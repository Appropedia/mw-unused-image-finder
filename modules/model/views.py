from collections.abc import Iterator
from modules.model import db
from modules.model import hashes

_hash_fields = ', '.join(f'H{i}' for i in range(8))

#Schema initialization function
@db.schema
def init_schema():
  con = db.get()

  con.execute(
    'CREATE VIEW IF NOT EXISTS pending_hashes (revision_id, revision_url) AS '
    'SELECT revisions.id, revisions.url FROM revisions WHERE revisions.id NOT IN '
    '(SELECT hashes.revision_id FROM hashes)')

  con.execute(
    f'CREATE VIEW IF NOT EXISTS image_hashes (image_title, {_hash_fields}) AS '
    f'SELECT images.title, {_hash_fields} FROM images '
    f'INNER JOIN revisions ON images.id = revisions.image_id '
    f'INNER JOIN hashes ON revisions.id = hashes.revision_id')

  con.execute(
    'CREATE VIEW IF NOT EXISTS image_revisions (image_title, revision_id) AS '
    'SELECT images.title, revisions.id FROM images '
    'INNER JOIN revisions ON images.id = revisions.image_id')

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

#Perform a search for images that are similar to a given one, within a maximum hamming distance
#Parameters:
# - image_title: The title of the reference image.
# - max_dist: The maximum allowed hamming distance. Image hashes farther than this are excluded.
#Return value: An iterator object that returns the titles of matching images.
def search_similar_images(image_title: str, max_dist: int) -> Iterator[str]:
  cursor = db.get().cursor()

  #Get the hash of the reference image
  ref_hash = cursor.execute(
    f'SELECT {_hash_fields} FROM image_hashes WHERE image_title = ?',
    (image_title,)).fetchone()

  if ref_hash is None: return

  #Perform a search for the reference hash and iterate over the results
  for revision_id in hashes.search(ref_hash, max_dist):
    #Obtain the next image title, then yield it
    row = cursor.execute(
      'SELECT image_title FROM image_revisions WHERE revision_id = ?',
      (revision_id,)).fetchone()

    #The reference image is similar to itself, so avoid returning it
    if row[0] == image_title:
      continue

    yield row[0]
