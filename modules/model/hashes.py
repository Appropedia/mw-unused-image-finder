from modules.model import db

#Schema initialization function
@db.schema
def init_schema():
  con = db.get()

  con.execute(
    f'CREATE TABLE IF NOT EXISTS hashes('
      f'revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE, '
      f'{', '.join(f'H{i} INT8' for i in range(8))})')

  for j in range(8):
    con.execute(
      f'CREATE INDEX IF NOT EXISTS hash_{j} ON hashes('
      f'{', '.join(f'H{i}' for i in range(j + 1))})')

#Create a new hash for a given image revision
def create(revision_id: int, hash_: tuple):
  con = db.get()
  con.execute(
    f'INSERT INTO hashes(revision_id, {', '.join(f'H{i}' for i in range(8))}) '
    f'VALUES ({', '.join('?' * 9)})',
    (revision_id,) + hash_)
  con.commit()
