from collections.abc import Iterator
from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  #This view allows to query URLs for images without a hash, allowing to download them
  db.get().execute(
    'CREATE VIEW IF NOT EXISTS pending_hashes_view(revision_id, revision_url) AS '
    'SELECT revisions.id, revisions.url FROM revisions WHERE revisions.id NOT IN '
    '(SELECT hashes.revision_id FROM hashes)')

#Return the count of revisions that haven't been hashed yet
def total() -> int:
  return db.get().execute('SELECT COUNT(*) FROM pending_hashes_view').fetchone()[0]

#Create an iterator object that returns the id and url of every revision that hasn't been hashed yet
def get() -> Iterator[tuple[int, str]]:
  con = db.get()

  while True:
    row = con.execute(
      'SELECT revision_id, revision_url FROM pending_hashes_view LIMIT 1').fetchone()
    if row is None: break
    yield row
