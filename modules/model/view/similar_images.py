from collections.abc import Iterator
from modules.model import db
from modules.model import hashes

_hash_fields = ', '.join(f'H{i}' for i in range(8))

#Schema initialization function
@db.schema
def init_schema():
  con = db.get()

  #This view allows to query the hash for an specific image
  con.execute(
    f'CREATE VIEW IF NOT EXISTS image_hashes_view(image_title, {_hash_fields}) AS '
    f'SELECT images.title, {_hash_fields} FROM images '
    f'INNER JOIN revisions ON images.id = revisions.image_id '
    f'INNER JOIN hashes ON revisions.id = hashes.revision_id')

  #This view allows to query the title for an specific revision
  con.execute(
    'CREATE VIEW IF NOT EXISTS image_revisions_view(image_title, revision_id) AS '
    'SELECT images.title, revisions.id FROM images '
    'INNER JOIN revisions ON images.id = revisions.image_id')

#Perform a search for images that are similar to a given one, within a maximum hamming distance
#Parameters:
# - image_title: The title of the reference image.
# - max_dist: The maximum allowed hamming distance. Image hashes farther than this are excluded.
#Return value: An iterator object that returns the titles of matching images.
def search(image_title: str, max_dist: int) -> Iterator[str]:
  cursor = db.get().cursor()

  #Get the hash of the reference image
  ref_hash = cursor.execute(
    f'SELECT {_hash_fields} FROM image_hashes_view WHERE image_title = ?',
    (image_title,)).fetchone()

  if ref_hash is None: return

  #Perform a search for the reference hash and iterate over the results
  for revision_id in hashes.search(ref_hash, max_dist):
    #Obtain the next image title, then yield it
    row = cursor.execute(
      'SELECT image_title FROM image_revisions_view WHERE revision_id = ?',
      (revision_id,)).fetchone()

    #The reference image is similar to itself, so avoid returning it
    if row[0] == image_title:
      continue

    yield row[0]
