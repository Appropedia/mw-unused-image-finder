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
      'status TEXT NOT NULL, '
      "CHECK (status IN ('new_pass', 'active', 'banned')))")

#Create a new user and return the new id
def create(name: str, password: str, status: str) -> int | None:
  with db.get() as con:
    row = con.execute(
      'INSERT INTO users (name, password, status) VALUES (?, ?, ?) ON CONFLICT (name) DO NOTHING '
      'RETURNING id',
      (name, generate_password_hash(password), status)).fetchone()

  return None if row is None else row[0]

#Read the id and status of a given user
def read(name: str) -> tuple[int, str] | tuple[None, None]:
  row = db.get().execute('SELECT id, status FROM users WHERE name = ?', (name,)).fetchone()

  return (None,) * 2 if row is None else row

#Check for user name availability
def name_available(name: str) -> bool:
  return bool(db.get().execute(
    'SELECT NOT EXISTS (SELECT 1 FROM users WHERE name = ?)', (name,)).fetchone()[0])

#Verify a user password and get their status
def authenticate(name: str, password: str) -> tuple[bool, str | None]:
  row = db.get().execute('SELECT password, status FROM users WHERE name = ?', (name,)).fetchone()
  if row is None:
    return (False, None)
  else:
    password_hash, status = row
    return (check_password_hash(password_hash, password), status)

#Update user password and status, returning True if successful (e.g. the user exists)
def update_password_and_status(name: str, password: str, status: str) -> bool:
  with db.get() as con:
    cursor = con.execute(
      'UPDATE users SET password = ?, status = ? WHERE name = ?',
      (generate_password_hash(password), status, name))

  return cursor.rowcount == 1
