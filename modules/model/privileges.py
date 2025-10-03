from modules.model import db

#Schema initialization function
@db.schema
def init_schema():
  db.get().execute(
    'CREATE TABLE IF NOT EXISTS privileges('
      'user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, '
      'name TEXT NOT NULL, '
      'UNIQUE (user_id, name), '
      'CHECK (name IN ("admin", "audit", "review")))')

#Grant a privilege to a given user
def create(user_id: int, name: str):
  with db.get() as con:
    con.execute('INSERT INTO privileges(user_id, name) VALUES (?, ?)', (user_id, name))
