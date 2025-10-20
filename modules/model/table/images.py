from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  db.get().execute(
    'CREATE TABLE IF NOT EXISTS images('
      'id INTEGER PRIMARY KEY, '
      'title TEXT UNIQUE NOT NULL)')

#Read an existing image id, or create an image and return its id in case it doesn't exist yet
def create_read_id(title: str) -> int:
  con = db.get()

  row = con.execute('SELECT id FROM images WHERE title = ?', (title,)).fetchone()
  if row is not None:
    return row[0]

  with con:
    row = con.execute(
      'INSERT INTO images (title) VALUES (?) RETURNING id', (title,)).fetchone()

  return row[0]

#Read the title of an image given its id
def read_title(id_: int) -> str | None:
  row = db.get().execute('SELECT title FROM images WHERE id = ?', (id_,)).fetchone()
  return None if row is None else row[0]

#Delete an image given its title
def delete(title: str) -> None:
  with db.get() as con:
    con.execute('DELETE FROM images WHERE title = ?', (title,))
