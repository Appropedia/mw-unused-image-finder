from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  db.get().execute(
    'CREATE VIEW IF NOT EXISTS user_privileges_view(user_name, privilege_name) AS '
    'SELECT users.name, privileges.name FROM users '
    'INNER JOIN privileges ON users.id = privileges.user_id')

#Get the user names of any previously registered administrator accounts
def get_administrator_names() -> tuple[str]:
  cursor = db.get().execute(
    'SELECT user_name FROM user_privileges_view WHERE privilege_name = "admin"')
  cursor.row_factory = lambda cur, row: row[0]
  return cursor.fetchall()

#Check whether a specific user has a given privilege
def check(user_name: str, privilege_name: str) -> bool:
  row = db.get().execute(
    'SELECT 1 FROM user_privileges_view WHERE user_name = ? AND privilege_name = ?',
    (user_name, privilege_name)).fetchone()

  return row is not None
