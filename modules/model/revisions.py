from collections.abc import Iterator
from modules.model import db

#Schema initialization function
@db.schema
def init_schema():
  con = db.get()

  con.execute(
    'CREATE TABLE IF NOT EXISTS revisions('
      'id INTEGER PRIMARY KEY, '
      'image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE, '
      'timestamp TEXT NOT NULL, '
      'size INTEGER, '
      'url TEXT NOT NULL, '
      'UNIQUE(image_id, timestamp))')

  con.execute(
    'CREATE INDEX IF NOT EXISTS revisions_timestamp ON revisions(timestamp)')

#Obtain the latest timestamp in the table, if any
def read_last_timestamp() -> str | None:
  row = db.get().execute(
    'SELECT timestamp FROM revisions ORDER BY timestamp DESC LIMIT 1').fetchone()
  return None if row is None else row[0]

#Create an iterator object that returns the timestamps associated to the revisions of a given image
#[development_only]
def read_timestamps(image_id: int) -> Iterator[str]:
  cursor = db.get().cursor()
  cursor.execute('SELECT timestamp FROM revisions WHERE image_id = ?', (image_id,))

  while True:
    row = cursor.fetchone()
    if row is None: break
    yield row[0]

#Create an iterator object that returns the timestamps and sizes associated to the revisions of a
#given image
#[development_only]
def read_timestamps_and_sizes(image_id: int) -> Iterator[tuple[str, int]]:
  cursor = db.get().cursor()
  cursor.execute('SELECT timestamp, size FROM revisions WHERE image_id = ?', (image_id,))

  while True:
    row = cursor.fetchone()
    if row is None: break
    yield row

#Update the size of an image revision
def update_size(id_: int, size: int):
  with db.get() as con:
    con.execute('UPDATE revisions SET size = ? WHERE id = ?', (size, id_))

#Start a full or partial synchronization process for the revisions table by creating a temporary
#tracking table
def synchronize_begin():
  db.get().execute(
    'CREATE TEMPORARY TABLE updated_revisions('
    'image_id INTEGER, '
    'timestamp TEXT)')

#Attempt to create a revision with the given data during a full or partial synchronization process,
#returning true if it was created
def synchronize_add_one(image_id: int, timestamp: str, url: str) -> bool:
  con = db.get()

  #Insert the revision only if it isn't in the table already
  with con:
    row = con.execute(
      'INSERT INTO revisions (image_id, timestamp, url) VALUES (?, ?, ?) '
      'ON CONFLICT (image_id, timestamp) DO NOTHING RETURNING 1',
      (image_id, timestamp, url)).fetchone()

  #Note: Table insertion order is important, as inserting into revisions first will cause other
  #restrictions such as foreign keys to be checked, causing an exception that skips the code below

  #Insert into the tracking table as well
  with con:
    con.execute(
      'INSERT INTO updated_revisions (image_id, timestamp) VALUES (?, ?)', (image_id, timestamp))

  #Return true if revision was inserted (did not fail the unique constraint check)
  return row is not None

#Create an iterator object that returns the image id and timestamp of all revisions that would be
#deleted by ending a full synchronization process
def full_synchronize_get_deletions() -> Iterator[tuple[int, str]]:
  cursor = db.get().cursor()
  cursor.execute(
    'SELECT image_id, timestamp FROM revisions WHERE (image_id, timestamp) NOT IN '
    '(SELECT image_id, timestamp FROM updated_revisions)')

  while True:
    row = cursor.fetchone()
    if row is None: break
    yield row

#Create an iterator object that returns the image id and timestamp of all revisions that would be
#deleted by ending a partial synchronization process
def partial_synchronize_get_deletions() -> Iterator[tuple[int, str]]:
  cursor = db.get().cursor()
  cursor.execute(
    'SELECT image_id, timestamp FROM revisions WHERE '
    'image_id IN (SELECT image_id FROM updated_revisions) '
    'AND NOT EXISTS (SELECT 1 FROM updated_revisions WHERE '
    'revisions.image_id = updated_revisions.image_id AND '
    'revisions.timestamp = updated_revisions.timestamp)')

  while True:
    row = cursor.fetchone()
    if row is None: break
    yield row

#End a full synchronization process for the revisions table by deleting all revisions that are not
#in the tracking table
def full_synchronize_end():
  con = db.get()

  with con:
    con.execute(
      'DELETE FROM revisions WHERE (image_id, timestamp) NOT IN '
      '(SELECT image_id, timestamp FROM updated_revisions)')

  con.execute('DROP TABLE updated_revisions')

#End a partial synchronization process for the revisions table by deleting all revisions of the
#images that have an image id in the tracking table but are missing a timestamp
def partial_synchronize_end():
  con = db.get()

  with con:
    con.execute(
      'DELETE FROM revisions WHERE image_id IN (SELECT image_id FROM updated_revisions) '
      'AND NOT EXISTS (SELECT 1 FROM updated_revisions WHERE '
      'revisions.image_id = updated_revisions.image_id AND '
      'revisions.timestamp = updated_revisions.timestamp)')

  con.execute('DROP TABLE updated_revisions')
