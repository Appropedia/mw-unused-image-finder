import enum
from modules.model import db

#Enumeration of operation results
class Status(enum.Enum):
  SUCCESS             = enum.auto()
  NAME_CONFLICT       = enum.auto()
  NON_EXISTENT_REASON = enum.auto()

#Schema initialization function
@db.schema
def init_schema() -> None:
  db.get().execute(
    'CREATE TABLE IF NOT EXISTS cleanup_reasons('
      'id INTEGER PRIMARY KEY, '
      'name TEXT UNIQUE NOT NULL, '
      'description TEXT NOT NULL)')

#Create a new cleanup reason
def create(name: str, description: str) -> Status:
  with db.get() as con:
    cursor = con.execute(
      'INSERT INTO cleanup_reasons (name, description) VALUES (?, ?) ON CONFLICT (name) DO NOTHING',
      (name, description))

    if cursor.rowcount != 1:
      return Status.NAME_CONFLICT

    return Status.SUCCESS

#Read the id of a cleanup reason given its name
def read_id(name: str) -> int:
  row = db.get().execute(
    'SELECT id FROM cleanup_reasons WHERE name = ?', (name,)).fetchone()
  return None if row is None else row[0]

#Read the description of a cleanup reason given its name
def read_description(name: str) -> str | None:
  row = db.get().execute(
    'SELECT description FROM cleanup_reasons WHERE name = ?', (name,)).fetchone()
  return None if row is None else row[0]

#Read all cleanup reason names
def read_name_all() -> list[str]:
  cursor = db.get().execute('SELECT name FROM cleanup_reasons')
  cursor.row_factory = lambda cur, row: row[0]
  return cursor.fetchall()

#Read all cleanup reason names and descriptions
def read_name_description_all() -> list[tuple[str, str]]:
  return db.get().execute('SELECT name, description FROM cleanup_reasons').fetchall()

#Update the name and description of a cleanup reason
def update(prev_name: str, new_name: str, description: str) -> Status:
  with db.get() as con:
    #This operation can be perturbed if other changes are made between reading and writing
    con.execute('BEGIN EXCLUSIVE')

    #Make sure the previous name exists before attempting to make modifications
    prev_name_exists = bool(con.execute(
      'SELECT EXISTS (SELECT 1 FROM cleanup_reasons WHERE name = ?)', (prev_name,)).fetchone()[0])

    if not prev_name_exists: return Status.NON_EXISTENT_REASON

    #Attempt to update. Since the previous name is confirmed to exist, the only way to cause no
    #modifications is because of a constraint violation.
    cursor = con.execute(
      'UPDATE OR IGNORE cleanup_reasons SET name = ?, description = ? WHERE name = ?',
      (new_name, description, prev_name))

  return Status.SUCCESS if cursor.rowcount == 1 else Status.NAME_CONFLICT

#Delete a cleanup reason
def delete(name: str) -> Status:
  with db.get() as con:
    cursor = con.execute('DELETE FROM cleanup_reasons WHERE name = ?', (name,))

    if cursor.rowcount != 1:
      return Status.NON_EXISTENT_REASON

    return Status.SUCCESS
