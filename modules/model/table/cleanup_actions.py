import enum
import sqlite3
from modules.model import db

#Enumeration of position swap directions
class Direction(enum.Enum):
  BACKWARD = enum.auto()
  FORWARD  = enum.auto()

#Enumeration of operation results
class Status(enum.Enum):
  SUCCESS             = enum.auto()
  NAME_CONFLICT       = enum.auto()
  POSITION_CONFLICT   = enum.auto()
  NON_EXISTENT_ACTION = enum.auto()

#Schema initialization function
@db.schema
def init_schema() -> None:
  db.get().execute(
    'CREATE TABLE IF NOT EXISTS cleanup_actions('
      'id INTEGER PRIMARY KEY, '
      'name TEXT UNIQUE NOT NULL, '
      'description TEXT NOT NULL, '
      'position INTEGER NOT NULL)')

#Create a new cleanup action, putting it at the last position
def create(name: str, description: str) -> Status:
  with db.get() as con:
    cursor = con.execute(
      'INSERT INTO cleanup_actions (name, description, position) '
      'VALUES (?, ?, (SELECT COUNT(*) FROM cleanup_actions)) ON CONFLICT (name) DO NOTHING',
      (name, description))

    if cursor.rowcount != 1:
      return Status.NAME_CONFLICT

    #This operation affects the position column so validation is required
    return _verify_positions_or_rollback(con)

#Read the id of a cleanup action given its name
def read_id(name: str) -> int:
  row = db.get().execute(
    'SELECT id FROM cleanup_actions WHERE name = ?', (name,)).fetchone()
  return None if row is None else row[0]

#Read the description of a cleanup action given its name
def read_description(name: str) -> str | None:
  row = db.get().execute(
    'SELECT description FROM cleanup_actions WHERE name = ?', (name,)).fetchone()
  return None if row is None else row[0]

#Read all cleanup actions and descriptions
def read_all() -> tuple[tuple[str, str], ...]:
  return db.get().execute(
    'SELECT name, description FROM cleanup_actions ORDER BY position ASC').fetchall()

#Update the name and description of a cleanup action
def update(prev_name: str, new_name: str, description: str) -> Status:
  with db.get() as con:
    #This operation can be perturbed if other changes are made between reading and writing
    con.execute('BEGIN EXCLUSIVE')

    #Make sure the previous name exists before attempting to make modifications
    prev_name_exists = bool(con.execute(
      'SELECT EXISTS (SELECT 1 FROM cleanup_actions WHERE name = ?)', (prev_name,)).fetchone()[0])

    if not prev_name_exists: return Status.NON_EXISTENT_ACTION

    #Attempt to update. Since the previous name is confirmed to exist, the only way to cause no
    #modifications is because of a constraint violation.
    cursor = con.execute(
      'UPDATE OR IGNORE cleanup_actions SET name = ?, description = ? WHERE name = ?',
      (new_name, description, prev_name))

  return Status.SUCCESS if cursor.rowcount == 1 else Status.NAME_CONFLICT

#Update the position of a cleanup action by swapping it with the one next to it
def swap(name: str, direction: Direction) -> Status:
  with db.get() as con:
    #This operation reads data and affects the position of two rows. Lock the database to prevent
    #concurrency problems.
    con.execute('BEGIN EXCLUSIVE')

    #Read the original position of the specified cleanup action, then validate the read
    row = con.execute('SELECT position FROM cleanup_actions WHERE name = ?', (name,)).fetchone()

    if row is None:
      return Status.NON_EXISTENT_ACTION

    old_pos = row[0]

    #Determine the last valid position based on the total row count
    end = con.execute('SELECT COUNT(*) - 1 FROM cleanup_actions').fetchone()[0]

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
      'UPDATE cleanup_actions SET position = IIF(position = :old_pos, :new_pos, :old_pos) '
      'WHERE position IN (:old_pos, :new_pos)', { 'old_pos': old_pos, 'new_pos': new_pos })

    #Make sure the swap affected both rows or rollback otherwise
    if cursor.rowcount != 2:
      con.execute('ROLLBACK')
      return Status.POSITION_CONFLICT

    #This operation affects the position column so validation is required
    return _verify_positions_or_rollback(con)

#Delete a cleanup action
def delete(name: str) -> Status:
  with db.get() as con:
    #Delete the action while obtaining the deleted position, then validate the result
    row = con.execute(
      'DELETE FROM cleanup_actions WHERE name = ? RETURNING position', (name,)).fetchone()

    if row is None:
      return Status.NON_EXISTENT_ACTION

    #Decrease the position of all actions that are after the deleted one
    con.execute(
      'UPDATE cleanup_actions SET position = position - 1 WHERE position > ?', (row[0],))

    #This operation affects the position column so validation is required
    return _verify_positions_or_rollback(con)

#Make sure the position column is consistent by asserting that all consecutive positions appear
#exactly once. Roll back the active transaction in case this condition fails to be met.
#Parameters:
# - con: The connection with an active transaction.
#Return value: The operation result as a status code
def _verify_positions_or_rollback(con: sqlite3.Connection) -> Status:
  #Check the conditions for consecutiveness:
  # - All positions are within the range from 0 to N-1, with N being the total row count.
  # - The amount of distinct positions matches the total row count.
  # - Special case: when the table becomes empty, the position column is deemed consistent.
  check_passed = bool(con.execute(
    'SELECT ('
      'MIN(position) = 0 AND '
      'MAX(position) = COUNT(*) - 1 AND '
      '(SELECT COUNT(DISTINCT position) FROM cleanup_actions) = COUNT(*)) '
    'OR COUNT(*) = 0 FROM cleanup_actions').fetchone()[0])

  if not check_passed:
    con.execute('ROLLBACK')

  return Status.SUCCESS if check_passed else Status.POSITION_CONFLICT
