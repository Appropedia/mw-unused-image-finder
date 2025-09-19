from collections.abc import Iterator
from modules.model import db
from modules.model import hashes

_hash_fields = ', '.join(f'H{i}' for i in range(8))

#Schema initialization function
@db.schema
def init_schema():
  con = db.get()

  #This view allows to query the hash for an specific image revision
  con.execute(
    f'CREATE VIEW IF NOT EXISTS '
    f'image_hashes_view(image_title, revision_timestamp, {_hash_fields}) AS '
    f'SELECT images.title, revisions.timestamp, {_hash_fields} FROM images '
    f'INNER JOIN revisions ON images.id = revisions.image_id '
    f'INNER JOIN hashes ON revisions.id = hashes.revision_id')

  #This view allows to query the title and timestamp for an specific revision
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'image_revisions_view(image_title, revision_id, revision_timestamp) AS '
    'SELECT images.title, revisions.id, revisions.timestamp FROM images '
    'INNER JOIN revisions ON images.id = revisions.image_id')

#Perform a search for images that are similar to a given one, within a maximum hamming distance
#Parameters:
# - image_title: The title of the reference image.
# - revision_timestamp: The timestamp of the reference image.
# - max_dist: The maximum allowed hamming distance. Image hashes farther than this are excluded.
#Return value: An iterator object that returns tuples with the titles and timestamps of matching
#images.
def search(image_title: int, revision_timestamp: int, max_dist: int) -> Iterator[tuple[str, int]]:
  cursor = db.get().cursor()

  #Get a hash of the reference image (any one will do)
  ref_hash = cursor.execute(
    f'SELECT {_hash_fields} FROM image_hashes_view '
    f'WHERE image_title = ? AND revision_timestamp = ? LIMIT 1',
    (image_title, revision_timestamp)).fetchone()

  if ref_hash is None: return     #Image is not hashed yet
  if ref_hash[0] is None: return  #Image couldn't be hashed (e.g. unsupported file type)

  #Perform a search for the reference hash and iterate over the results
  for revision_id in hashes.search(ref_hash, max_dist):
    #Obtain the next image title, then yield it
    row = cursor.execute(
      'SELECT image_title, revision_timestamp FROM image_revisions_view '
      'WHERE revision_id = ? LIMIT 1',
      (revision_id,)).fetchone()

    if row[0] == image_title:
      continue  #The reference image is similar to itself, so avoid returning it

    print(revision_timestamp, row[1])
    yield row
