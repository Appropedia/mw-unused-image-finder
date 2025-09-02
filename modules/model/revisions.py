from collections.abc import Iterator
from modules.model import db

#Schema initialization function
@db.schema
def init_schema():
  db.get().execute(
    'CREATE TABLE IF NOT EXISTS revisions('
      'id INTEGER PRIMARY KEY, '
      'image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE, '
      'timestamp INTEGER NOT NULL, '
      'size INTEGER, '
      'url STRING NOT NULL, '
      'UNIQUE(image_id, timestamp))')

#Create a revision with the given data and return its id
def create(image_id: int, timestamp: int, url: str) -> int:
  con = db.get()
  row = con.execute(
    'INSERT INTO revisions(image_id, timestamp, url) VALUES (?, ?, ?) '
    'ON CONFLICT (image_id, timestamp) DO NOTHING RETURNING id',
    (image_id, timestamp, url)).fetchone()
  con.commit()
  return None if row is None else row[0]

#Obtain the latest timestamp in the table, if any
def read_last_timestamp() -> int | None:
  row = db.get().execute(
    'SELECT timestamp FROM revisions ORDER BY timestamp DESC LIMIT 1').fetchone()
  return None if row is None else row[0]

#Create an iterator object that returns the timestamps associated to the revisions of a given image
def read_timestamps(image_id: int) -> Iterator[int]:
  cursor = db.get().cursor()
  cursor.row_factory = lambda cur, row: row[0]
  cursor.execute('SELECT timestamp FROM revisions WHERE image_id = ?', (image_id,))

  while True:
    row = cursor.fetchone()
    if row is None: break
    yield row

#Update the size of an image revision
def update_size(id_: int, size: int):
  con = db.get()
  con.execute('UPDATE revisions SET size = ? WHERE id = ?', (size, id_))
  con.commit()

#Delete a revision given its uniquely identifying fields
def delete(image_id: int, timestamp: int):
  con = db.get()
  con.execute('DELETE FROM revisions WHERE image_id = ? AND timestamp = ?', (image_id, timestamp))
  con.commit()
