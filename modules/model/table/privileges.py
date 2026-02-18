from modules.model import db

VALID_PRIVILEGES = ('admin', 'plan', 'review')

#Schema initialization function
@db.schema
def init_schema() -> None:
  db.get().execute(
    'CREATE TABLE IF NOT EXISTS privileges('
      'user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, '
      'name TEXT NOT NULL, '
      'UNIQUE (user_id, name), '
      f'CHECK (name IN ({', '.join(f"'{p}'" for p in VALID_PRIVILEGES)})))')

#Grant a privilege to a given user
def create(user_id: int, name: str) -> None:
  with db.get() as con:
    con.execute(
      'INSERT INTO privileges (user_id, name) VALUES (?, ?) ON CONFLICT (user_id, name) DO NOTHING',
      (user_id, name))

#Revoke a privilege to a given user
def delete(user_id: int, name: str) -> None:
  with db.get() as con:
    con.execute('DELETE FROM privileges WHERE user_id = ? AND name = ?', (user_id, name))
