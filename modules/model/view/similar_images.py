from modules.model import db
from modules.model.table import hashes, unused_images
from modules.model.view import image_revisions, review_details

_hash_fields = ', '.join(f'H{i}' for i in range(8))

#Schema initialization function
@db.schema
def init_schema() -> None:
  #This view allows to query for the timestamp and one of the hashes for each revision of a specific
  #image
  db.get().execute(
    f'CREATE VIEW IF NOT EXISTS '
    f'reference_hashes_view(image_id, revision_timestamp, {_hash_fields}) AS '
    f'SELECT image_id, timestamp, {_hash_fields} FROM '
      f'(SELECT revisions.image_id, revisions.timestamp, {_hash_fields}, '
      f'ROW_NUMBER() OVER (PARTITION BY revisions.id) AS row_num FROM revisions '
      f'INNER JOIN hashes ON revisions.id = hashes.revision_id)'
    f'WHERE row_num = 1')

#Perform a search for revisions that are similar to the revisions of a given image, within a maximum
#hamming distance
#Parameters:
# - ref_image_id: The id of the reference image.
# - max_dist: The maximum allowed hamming distance. Image hashes farther than this are excluded.
#Return value: A nested dictionary that encodes matching images with the following structure:
#   Search results
#   <dict>
#     - key: {Timestamp of the revision of the reference image}
#       <dict>
#       - key: {Title of the matching image}
#         <dict>
#         - key: 'unused'
#           <bool> - a flag indicating whether the image is unused in the wiki
#         - key: 'revisions'
#           <list[str]> - the timestamps of all matching revisions
def search(ref_image_id: int, max_dist: int) -> dict[str, dict[str, dict[str, bool | list[str]]]]:
  con = db.get()

  #Obtain the timestamp and a reference hash for each of the revisions of the given image (every
  #revision can have up to 4 hashes - one per rotation, but any one will do)
  ref_hash_cursor = con.execute(
    f'SELECT revision_timestamp, {_hash_fields} FROM reference_hashes_view WHERE image_id = ?',
    (ref_image_id,))
  ref_hash_cursor.row_factory = lambda cur, row: (row[0],
                                                  None if None in row[1:9] else bytes(row[1:9]))

  result = {}
  for ref_revision_timestamp, ref_hash in ref_hash_cursor:
    #Make sure the image is hashed (e.g. not an unsupported file type)
    if ref_hash is None:
      continue

    #Perform a search for the reference hash and iterate over the results
    result[ref_revision_timestamp] = {}
    for match_revision_id in hashes.search(ref_hash, max_dist):
      #Look up the image and timestamp that correspond to the revision that was just found
      match_image_id, match_image_title, match_rev_timestamp =\
        image_revisions.get_revision_info(match_revision_id)

      #Make sure this is different from the reference image, which is identical to itself
      if match_image_id == ref_image_id:
        continue

      #Add a dictionary for the matching image if not already present
      if match_image_title not in result[ref_revision_timestamp]:
        result[ref_revision_timestamp][match_image_title] = {
          'unused': unused_images.exists(match_image_title),
          'reviewed': review_details.exists(match_image_title),
          'revisions': [],
        }

      #Lastly, append the matching revision timestamp
      result[ref_revision_timestamp][match_image_title]['revisions'].append(match_rev_timestamp)

  return result
