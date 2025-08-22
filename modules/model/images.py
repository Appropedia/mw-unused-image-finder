from modules.model import db

#Schema initialization function
@db.schema
def init_schema():
  db.get().execute(
    'CREATE TABLE IF NOT EXISTS images('
      'id INTEGER PRIMARY KEY, '
      'title STRING UNIQUE NOT NULL)')

#Create an image with a given title and return its id
def create(title: str) -> int:
  con = db.get()
  row = con.execute(
    'INSERT INTO images(title) VALUES (?) ON CONFLICT (title) DO NOTHING RETURNING id',
    (title,)).fetchone()
  con.commit()
  return None if row is None else row[0]

#Read the id of an image given its title
def read_id(title: str) -> int:
  row = db.get().execute('SELECT id FROM images WHERE title = ?', (title,)).fetchone()
  return None if row is None else row[0]

#Attempt to create an image and return its id, or simply return its id if it already exists
def create_read_id(title: str) -> int:
  id_ = create(title)
  return id_ if id_ is not None else read_id(title)

#Delete an image given its title
def delete(title: str):
  con = db.get()
  con.execute('DELETE FROM images WHERE title = ?', (title,))
  con.commit()
