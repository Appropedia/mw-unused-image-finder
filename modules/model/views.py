from modules.model import db
from collections.abc import Iterator

#Schema initialization function
@db.schema
def init_schema():
  db.get().execute(
    'CREATE VIEW IF NOT EXISTS pending_hashes (revision_id, revision_url) AS '
    'SELECT revisions.id, revisions.url FROM revisions WHERE revisions.id NOT IN '
    '(SELECT hashes.revision_id FROM hashes)')

#Return the count of revisions that haven't been hashed yet
def pending_hash_total() -> int:
  return db.get().execute('SELECT COUNT(1) FROM pending_hashes').fetchone()[0]

#Create an iterator object that returns the id and url of every revision that hasn't been hashed yet
def pending_hashes() -> Iterator[tuple[int, str]]:
  cursor = db.get().cursor()
  cursor.execute('SELECT revision_id, revision_url FROM pending_hashes')

  while True:
    row = cursor.fetchone()
    if row is None: break
    yield row
