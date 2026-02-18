from werkzeug.security import generate_password_hash, check_password_hash
from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  db.get().execute(
    'CREATE TABLE IF NOT EXISTS users('
      'id INTEGER PRIMARY KEY, '
      'name TEXT UNIQUE NOT NULL, '
      'password TEXT NOT NULL, '
      'password_reset BOOLEAN NOT NULL, '
      'ban_status BOOLEAN NOT NULL DEFAULT FALSE)')

#Create a new user and return the new id
def create(name: str, password: str, password_reset: bool) -> int | None:
  with db.get() as con:
    row = con.execute(
      'INSERT INTO users (name, password, password_reset) VALUES (?, ?, ?) '
      'ON CONFLICT (name) DO NOTHING RETURNING id',
      (name, generate_password_hash(password), password_reset)).fetchone()

  return None if row is None else row[0]

#Read the id of a given user
def read_id(name: str) -> str | None:
  row = db.get().execute('SELECT id FROM users WHERE name = ?', (name,)).fetchone()

  return None if row is None else row[0]

#Read the id and status flags of a given user
def read_id_status(name: str) -> tuple[int, bool, bool] | tuple[None, None, None]:
  row = db.get().execute(
    'SELECT id, password_reset, ban_status FROM users WHERE name = ?', (name,)).fetchone()

  return (None,) * 3 if row is None else row

#Read the names of all users
def read_name_all() -> list[str]:
  cursor = db.get().execute('SELECT name FROM users')
  cursor.row_factory = lambda cur, row: row[0]
  return cursor.fetchall()

#Read the names and status flags of all users
def read_name_status_all() -> list[dict[str, str | bool]]:
  cursor = db.get().execute('SELECT name, password_reset, ban_status FROM users')
  cursor.row_factory = lambda cur, row: { 'name': row[0],
                                          'password_reset': bool(row[1]),
                                          'ban_status': bool(row[2]) }
  return cursor.fetchall()

#Check whether a user name is registered already
def exists(name: str) -> bool:
  return bool(db.get().execute(
    'SELECT EXISTS (SELECT 1 FROM users WHERE name = ?)', (name,)).fetchone()[0])

#Verify a user password and get their ban status
def authenticate(name: str, password: str) -> tuple[bool, bool | None]:
  row = db.get().execute(
    'SELECT password, ban_status FROM users WHERE name = ?', (name,)).fetchone()
  if row is None:
    return False, None
  else:
    password_hash, ban_status = row
    return check_password_hash(password_hash, password), ban_status

#Update user password and password reset status, returning True if successful (e.g. the user exists)
def update_password_and_reset_status(name: str, password: str, password_reset: bool) -> bool:
  with db.get() as con:
    cursor = con.execute(
      'UPDATE users SET password = ?, password_reset = ? WHERE name = ?',
      (generate_password_hash(password), password_reset, name))

  return cursor.rowcount == 1

#Update the ban status of a given user
def update_ban_status(id_: int, ban_status: bool):
  with db.get() as con:
    con.execute('UPDATE users SET ban_status = ? WHERE id = ?', (ban_status, id_))

#Delete a user account
def delete(name: str) -> None:
  with db.get() as con:
    con.execute('DELETE FROM users WHERE name = ?', (name,))
