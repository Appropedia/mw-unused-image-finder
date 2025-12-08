from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  con = db.get()

  con.execute(
    'CREATE TABLE IF NOT EXISTS hashes('
      'revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE, '
      'hash INT)')

  con.execute(
    'CREATE INDEX IF NOT EXISTS hashes_revision_id ON hashes(revision_id)')

#Create a new hash for a given image revision
def create(revision_id: int, hash_: int | None) -> None:
  with db.get() as con:
    con.execute(f'INSERT INTO hashes (revision_id, hash) VALUES (?, ?)', (revision_id, hash_))

#Get all image hashes that are within a maximum hamming distance from a given reference hash
def search(ref_hash: int, max_dist: int) -> list[int]:
  db.load_extension('hammdist')
  con = db.get()

  cursor = con.execute(
    'SELECT revision_id FROM hashes WHERE hash IS NOT NULL AND HAMMDIST(?, hash) <= ?',
    (ref_hash, max_dist))

  cursor.row_factory = lambda cur, row: row[0]

  return cursor.fetchall()
