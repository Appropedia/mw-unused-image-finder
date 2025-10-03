from modules.model import db

#Schema initialization function
@db.schema
def init_schema():
  db.get().execute(
    'CREATE TABLE IF NOT EXISTS images('
      'id INTEGER PRIMARY KEY, '
      'title TEXT UNIQUE NOT NULL)')

#Create an image with a given title and return its id
def create(title: str) -> int | None:
  with db.get() as con:
    row = con.execute(
      'INSERT INTO images (title) VALUES (?) ON CONFLICT (title) DO NOTHING RETURNING id',
      (title,)).fetchone()
  return None if row is None else row[0]

#Attempt to create an image and return its id, or simply return its id if it already exists
def create_read_id(title: str) -> int:
  id_ = create(title)
  return id_ if id_ is not None else read_id(title)

#Read the id of an image given its title
def read_id(title: str) -> int | None:
  row = db.get().execute('SELECT id FROM images WHERE title = ?', (title,)).fetchone()
  return None if row is None else row[0]

#Read the title of an image given its id
def read_title(id_: int) -> str | None:
  row = db.get().execute('SELECT title FROM images WHERE id = ?', (id_,)).fetchone()
  return None if row is None else row[0]

#Delete an image given its title
def delete(title: str):
  with db.get() as con:
    con.execute('DELETE FROM images WHERE title = ?', (title,))

#Delete any image that has no revisions (used for pruning after fully synchronizing revisions)
def delete_revision_lacking():
  with db.get() as con:
    con.execute('DELETE FROM images WHERE id NOT IN (SELECT image_id FROM revisions)')
