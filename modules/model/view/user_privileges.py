from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  #This view allows to query for the privileges of a specific user
  db.get().execute(
    'CREATE VIEW IF NOT EXISTS user_privileges_view(user_name, privilege_name) AS '
    'SELECT users.name, privileges.name FROM users '
    'INNER JOIN privileges ON users.id = privileges.user_id')

#Get the privileges of a given user
def get(user_name: str) -> list[str]:
  cursor = db.get().execute(
    'SELECT privilege_name FROM user_privileges_view WHERE user_name = ?', (user_name,))
  cursor.row_factory = lambda cur, row: row[0]
  return cursor.fetchall()

#Get the user names of any previously registered administrator accounts
def get_administrator_names() -> list[str]:
  cursor = db.get().execute(
    'SELECT user_name FROM user_privileges_view WHERE privilege_name = "admin"')
  cursor.row_factory = lambda cur, row: row[0]
  return cursor.fetchall()
