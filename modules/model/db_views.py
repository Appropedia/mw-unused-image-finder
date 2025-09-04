from collections.abc import Iterator
import enum
from modules.model import db
from modules.model import hashes

_hash_fields = ', '.join(f'H{i}' for i in range(8))

#Enumerations for query parameters
class Usage(enum.Enum):
  unused    = enum.auto()
  used      = enum.auto()
  any       = enum.auto()

class SortBy(enum.Enum):
  all_rev_size = enum.auto()
  max_rev_size = enum.auto()
  title        = enum.auto()
  timestamp    = enum.auto()

class SortOrder(enum.Enum):
  asc  = enum.auto()
  desc = enum.auto()

#Schema initialization function
@db.schema
def init_schema():
  con = db.get()

  #This view allows to query URLs for images without a hash, allowing to download them
  con.execute(
    'CREATE VIEW IF NOT EXISTS pending_hashes_view(revision_id, revision_url) AS '
    'SELECT revisions.id, revisions.url FROM revisions WHERE revisions.id NOT IN '
    '(SELECT hashes.revision_id FROM hashes)')

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

  #This view allows to query information for all revisions of all unused images
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'unused_image_revisions_view(image_title, revision_timestamp, revision_size) AS '
    'SELECT images.title, revisions.timestamp, revisions.size FROM images '
    'INNER JOIN revisions ON images.id = revisions.image_id '
    'WHERE images.title IN (SELECT unused_images.title FROM unused_images)')

  #This view allows to query information for all revisions of all images in use
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'used_image_revisions_view(image_title, revision_timestamp, revision_size) AS '
    'SELECT images.title, revisions.timestamp, revisions.size FROM images '
    'INNER JOIN revisions ON images.id = revisions.image_id '
    'WHERE images.title NOT IN (SELECT unused_images.title FROM unused_images)')

  #This view allows to query information for all but the newest revision of all images in use
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'older_used_image_revisions_view(image_title, revision_timestamp, revision_size) AS '
    'SELECT image_title, revision_timestamp, revision_size FROM used_image_revisions_view AS t1 '
    'WHERE revision_timestamp NOT IN '
      '(SELECT MAX(revision_timestamp) FROM used_image_revisions_view AS t2 '
      'WHERE t1.image_title = t2.image_title GROUP BY t2.image_title)')

#Return the count of revisions that haven't been hashed yet
def pending_hash_total() -> int:
  return db.get().execute('SELECT COUNT(*) FROM pending_hashes_view').fetchone()[0]

#Create an iterator object that returns the id and url of every revision that hasn't been hashed yet
def pending_hashes() -> Iterator[tuple[int, str]]:
  cursor = db.get().cursor()
  cursor.execute('SELECT revision_id, revision_url FROM pending_hashes_view')

  while True:
    row = cursor.fetchone()
    if row is None: break
    yield row

#Create an iterator object that returns general information about images
#Parameters:
# - usage: Indicates wheter the requested images are used in an article.
#   - Usage.unused: The images are not used in any article.
#   - Usage.used: The images are used by one or more articles.
#   - Usage.any: The images are returned regardless of usage.
# - include_newest: For used images, whether to consider the latest revision. If false the returned
#   data and sorting options will not reflect or consider said revision.
# - sort_by: Indicates the ordering criterion.
#   - SortBy.all_rev_size: Sort by the sum of the sizes of all considered revisions of every image.
#   - SortBy.max_rev_size: Sort by the maximum size of considered revisions of every image.
#   - SortBy.title: Sort by image image title.
#   - SortBy.timestamp: Sort by the latest of considered revisions of every image.
# - sort_order: Indicates the ordering direction.
#   - SortOrder.asc: Ascending order.
#   - SortOrder.desc: Descending order.
# - limit: Maximum allowed number of rows to return.
# - offset: The starting row offset.
def search_images(usage: Usage, include_newest: bool, sort_by: SortBy, sort_order: SortOrder,
                  limit: int = 10, offset: int = 0) -> Iterator[str, int, int, int, int]:
  cursor = db.get().cursor()

  #Validate simple arguments and derive their SQL expressions
  match sort_by:
    case SortBy.all_rev_size: sort_expr = 'SUM(revision_size)'
    case SortBy.max_rev_size: sort_expr = 'MAX(revision_size)'
    case SortBy.title:        sort_expr = 'image_title'
    case SortBy.timestamp:    sort_expr = 'revision_timestamp'
    case _:                   raise ValueError(f'Invalid value for sort_by: {sort_by}')

  match sort_order:
    case SortOrder.asc:  order_expr = 'ASC'
    case SortOrder.desc: order_expr = 'DESC'
    case _:              raise ValueError(f'Invalid value for sort_order: {sort_order}')

  #Set template strings for all queries
  query_base = 'SELECT image_title, MAX(revision_timestamp), COUNT(*), SUM(revision_size), '\
               'MAX(revision_size) '\
               'FROM {view} WHERE revision_size IS NOT NULL GROUP BY image_title '

  query_end = f'ORDER BY {sort_expr} {order_expr} LIMIT ? OFFSET ?'

  #Validate related arguments and derive the final query string
  match usage:
    case Usage.unused:
      #Will look for all revisions in unused images
      query_str = query_base.format(view = 'unused_image_revisions_view') + query_end
    case Usage.used:
      if include_newest:
        #Will look for all revisions in used images
        query_str = query_base.format(view = 'used_image_revisions_view') + query_end
      else:
        #Will look for older revisions in used images
        query_str = query_base.format(view = 'older_used_image_revisions_view') + query_end
    case Usage.any:
      if include_newest:
        used_image_view = 'used_image_revisions_view'
      else:
        used_image_view = 'older_used_image_revisions_view'

      #Will look for all revisions in unused images and either all or older revisions in used images
      query_str = query_base.format(view = 'unused_image_revisions_view') + 'UNION ALL ' +\
                  query_base.format(view = used_image_view) + query_end
    case _:
      raise ValueError(f'Invalid value for usage: {usage}')

  cursor.execute(query_str, (limit, offset))

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
