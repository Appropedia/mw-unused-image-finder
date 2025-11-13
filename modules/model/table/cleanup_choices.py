import enum
import sqlite3
from modules.model import db

#Enumeration of position swap directions
class Direction(enum.Enum):
  BACKWARD = enum.auto()
  FORWARD  = enum.auto()

#Enumeration of operation results
class Status(enum.Enum):
  SUCCESS           = enum.auto()
  LINK_CONFLICT     = enum.auto()
  POSITION_CONFLICT = enum.auto()
  NON_EXISTENT_LINK = enum.auto()

#Schema initialization function
@db.schema
def init_schema() -> None:
  db.get().execute(
    'CREATE TABLE IF NOT EXISTS cleanup_choices('
      'cleanup_action_id INTEGER NOT NULL REFERENCES cleanup_actions(id) ON DELETE CASCADE, '
      'cleanup_reason_id INTEGER NOT NULL REFERENCES cleanup_reasons(id) ON DELETE CASCADE, '
      'position INTEGER NOT NULL, '
      'UNIQUE (cleanup_action_id, cleanup_reason_id))')

#Create a new action/reason link, putting it at the last position of its action group
def create(cleanup_action_id: int, cleanup_reason_id: int) -> Status:
  with db.get() as con:
    cursor = con.execute(
      'INSERT INTO cleanup_choices (cleanup_action_id, cleanup_reason_id, position) '
      'VALUES (:cleanup_action_id, :cleanup_reason_id, '
        '(SELECT COUNT(*) FROM cleanup_choices WHERE cleanup_action_id = :cleanup_action_id)) '
      'ON CONFLICT(cleanup_action_id, cleanup_reason_id) DO NOTHING',
      { 'cleanup_action_id': cleanup_action_id, 'cleanup_reason_id': cleanup_reason_id })

    if cursor.rowcount != 1:
      return Status.LINK_CONFLICT

    #This operation affects the position column within an action group so validation is required
    return _verify_positions_or_rollback(con, cleanup_action_id)

#Update the position of an action/reason link by swapping it with the one next to it in the same
#action group
def swap(cleanup_action_id: int, cleanup_reason_id: int, direction: Direction) -> Status:
  with db.get() as con:
    #This operation reads data and affects the position of two rows. Lock the database to prevent
    #concurrency problems.
    con.execute('BEGIN EXCLUSIVE')

    #Read the original position of the specified action/reason link, then validate the read
    row = con.execute(
      'SELECT position FROM cleanup_choices WHERE cleanup_action_id = ? AND cleanup_reason_id = ?',
      (cleanup_action_id, cleanup_reason_id,)).fetchone()

    if row is None:
      return Status.NON_EXISTENT_LINK

    old_pos = row[0]

    #Determine the last valid position based on the action group size
    end = con.execute(
      'SELECT COUNT(*) - 1 FROM cleanup_choices WHERE cleanup_action_id = ?',
      (cleanup_action_id,)).fetchone()[0]

    #Validate the direction and original position, then calculate the new position
    match direction:
      case Direction.BACKWARD:
        if old_pos <= 0:
          return Status.POSITION_CONFLICT
        new_pos = old_pos - 1
      case Direction.FORWARD:
        if old_pos >= end:
          return Status.POSITION_CONFLICT
        new_pos = old_pos + 1
      case _:
        raise ValueError(f'Invalid direction: {direction}')

    #Swap the row positions
    cursor = con.execute(
      'UPDATE cleanup_choices SET position = IIF(position = :old_pos, :new_pos, :old_pos) '
      'WHERE cleanup_action_id = :cleanup_action_id AND position IN (:old_pos, :new_pos)',
      { 'cleanup_action_id': cleanup_action_id, 'old_pos': old_pos, 'new_pos': new_pos })

    #Make sure the swap affected both rows or rollback otherwise
    if cursor.rowcount != 2:
      con.execute('ROLLBACK')
      return Status.POSITION_CONFLICT

    #This operation affects the position column within an action group so validation is required
    return _verify_positions_or_rollback(con, cleanup_action_id)

#Delete a action/reason link
def delete(cleanup_action_id: int, cleanup_reason_id: int) -> Status:
  with db.get() as con:
    #Delete the link while obtaining the deleted position, then validate the result
    row = con.execute(
      'DELETE FROM cleanup_choices WHERE cleanup_action_id = ? AND cleanup_reason_id = ? '
      'RETURNING position', (cleanup_action_id, cleanup_reason_id)).fetchone()

    if row is None:
      return Status.NON_EXISTENT_LINK

    #Decrease the position of all links in the same action group that are after the deleted one
    con.execute(
      'UPDATE cleanup_choices SET position = position - 1 '
      'WHERE cleanup_action_id = ? AND position > ?', (cleanup_action_id, row[0]))

    #This operation affects the position column within an action group so validation is required
    return _verify_positions_or_rollback(con, cleanup_action_id)

#Make sure the position column is consistent by asserting that all consecutive positions appear
#exactly once for a given action group. Roll back the active transaction in case this condition
#fails to be met.
#Parameters:
# - con: The connection with an active transaction.
# - cleanup_action_id: Identifies the action group to be verified.
#Return value: The operation result as a status code
def _verify_positions_or_rollback(con: sqlite3.Connection, cleanup_action_id: int) -> Status:
  #Check the conditions for consecutiveness:
  # - All positions are within the range from 0 to N-1, with N being the action group size.
  # - The amount of distinct positions matches the action group size.
  # - Special case: when the action group becomes empty, the position column is deemed consistent.
  check_passed = bool(con.execute(
    'WITH action_group AS (SELECT position FROM cleanup_choices WHERE cleanup_action_id = ?) '
    'SELECT ('
      'MIN(position) = 0 AND '
      'MAX(position) = COUNT(*) - 1 AND '
      '(SELECT COUNT(DISTINCT position) FROM action_group) = COUNT(*)) '
    'OR COUNT(*) = 0 FROM action_group', (cleanup_action_id,)).fetchone()[0])

  if not check_passed:
    con.execute('ROLLBACK')

  return Status.SUCCESS if check_passed else Status.POSITION_CONFLICT
