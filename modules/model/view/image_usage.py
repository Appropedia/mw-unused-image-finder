from collections.abc import Iterator
import enum
from modules.model import db

#Enumerations for query parameters
class QueryParams:
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
def search(usage: QueryParams.Usage,
           include_newest: bool,
           sort_by: QueryParams.SortBy,
           sort_order: QueryParams.SortOrder,
           limit: int = 10,
           offset: int = 0) -> Iterator[str, int, int, int, int]:
  cursor = db.get().cursor()

  #Validate simple arguments and derive their SQL expressions
  match sort_by:
    case QueryParams.SortBy.all_rev_size: sort_expr = 'SUM(revision_size)'
    case QueryParams.SortBy.max_rev_size: sort_expr = 'MAX(revision_size)'
    case QueryParams.SortBy.title:        sort_expr = 'image_title'
    case QueryParams.SortBy.timestamp:    sort_expr = 'revision_timestamp'
    case _:                               raise ValueError(f'Invalid value for sort_by: {sort_by}')

  match sort_order:
    case QueryParams.SortOrder.asc:  order_expr = 'ASC'
    case QueryParams.SortOrder.desc: order_expr = 'DESC'
    case _:                          raise ValueError(f'Invalid value for sort_order: {sort_order}')

  #Set template strings for all queries
  query_base = 'SELECT image_title, MAX(revision_timestamp), COUNT(*), SUM(revision_size), '\
               'MAX(revision_size) '\
               'FROM {view} WHERE revision_size IS NOT NULL GROUP BY image_title '

  query_end = f'ORDER BY {sort_expr} {order_expr} LIMIT ? OFFSET ?'

  #Validate related arguments and derive the final query string
  match usage:
    case QueryParams.Usage.unused:
      #Will look for all revisions in unused images
      query_str = query_base.format(view = 'unused_image_revisions_view') + query_end
    case QueryParams.Usage.used:
      if include_newest:
        #Will look for all revisions in used images
        query_str = query_base.format(view = 'used_image_revisions_view') + query_end
      else:
        #Will look for older revisions in used images
        query_str = query_base.format(view = 'older_used_image_revisions_view') + query_end
    case QueryParams.Usage.any:
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
