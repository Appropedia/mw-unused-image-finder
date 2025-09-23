from werkzeug.security import generate_password_hash, check_password_hash
from modules.model import db

#Schema initialization function
@db.schema
def init_schema():
  db.get().execute(
    'CREATE TABLE IF NOT EXISTS users('
      'id INTEGER PRIMARY KEY, '
      'name TEXT UNIQUE NOT NULL, '
      'password TEXT NOT NULL, '
      'status TEXT NOT NULL, '
      'CHECK (status IN ("new_pass", "active", "banned")))')

#Create a new user
def create(name: str, password: str, status: str):
  with db.get() as con:
    con.execute(
      'INSERT INTO users(name, password, status) VALUES (?, ?, ?)',
      (name, generate_password_hash(password), status))

#Verify a user password and get their status
def authenticate(name: str, password: str) -> tuple[bool, str]:
  row = db.get().execute('SELECT password, status FROM users WHERE name = ?', (name,)).fetchone()
  if row is None:
    return (False, None)
  else:
    password_hash, status = row
    return (check_password_hash(password_hash, password), status)

#Return the users total (TEMPORARY METHOD - used for checking admin account existence)
#[development_only]
def total() -> int:
  return db.get().execute('SELECT COUNT(*) FROM users').fetchone()[0]
