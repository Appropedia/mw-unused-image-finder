import enum
from modules.model import db

#Enumeration of image usage categories with information related to each
class Category(enum.Enum):
  unused_img_all_rev     = { 'view':  'unused_image_all_revisions_view',
                             'order': 'ORDER BY order_param DESC, image_id ASC', }
  used_img_old_rev       = { 'view':  'used_image_old_revisions_view',
                             'order': 'ORDER BY order_param DESC, image_id ASC', }
  used_img_all_rev       = { 'view':  'used_image_all_revisions_view',
                             'order': 'ORDER BY order_param DESC, image_id ASC', }
  used_img_all_rev_count = { 'view':  'used_image_all_revisions_count_view',
                             'order': 'ORDER BY order_param DESC, image_id ASC', }

#Schema initialization function
@db.schema
def init_schema() -> None:
  con = db.get()

  #This view allows to query for the next unused image with the largest combined size of all of its
  #revisions
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'unused_image_all_revisions_view(image_id, image_title, order_param) AS '
    'SELECT images.id, images.title, SUM(revisions.size) FROM images '
    'INNER JOIN revisions ON images.id = revisions.image_id '
    'WHERE images.title IN (SELECT unused_images.title FROM unused_images) '
    'GROUP BY images.id ORDER BY SUM(revisions.size) DESC, images.id ASC')

  #This view allows to query for the next used image with the largest combined size of all of its
  #older revisions
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'used_image_old_revisions_view(image_id, image_title, order_param) AS '
    'SELECT image_id, image_title, SUM(revision_size) FROM '
      '(SELECT images.id as image_id, images.title as image_title, '
      'revisions.size as revision_size, revisions.timestamp as revision_timestamp FROM images '
      'INNER JOIN revisions ON images.id = revisions.image_id '
      'WHERE images.title NOT IN (SELECT unused_images.title FROM unused_images)) '
    'WHERE revision_timestamp NOT IN '
      '(SELECT MAX(revisions.timestamp) FROM images '
      'INNER JOIN revisions ON images.id = revisions.image_id '
      'WHERE images.id = image_id GROUP BY images.id)'
    'GROUP BY image_id ORDER BY SUM(revision_size) DESC, image_id ASC')

  #This view allows to query for the next used image with the largest combined size of all of its
  #revisions
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'used_image_all_revisions_view(image_id, image_title, order_param) AS '
    'SELECT images.id, images.title, SUM(revisions.size) FROM images '
    'INNER JOIN revisions ON images.id = revisions.image_id '
    'WHERE images.title NOT IN (SELECT unused_images.title FROM unused_images) '
    'GROUP BY images.id ORDER BY SUM(revisions.size) DESC, images.id ASC')

  #This view allows to query for the next used image with the largest amount of revisions
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'used_image_all_revisions_count_view(image_id, image_title, order_param) AS '
    'SELECT images.id, images.title, COUNT(*) FROM images '
    'INNER JOIN revisions ON images.id = revisions.image_id '
    'WHERE images.title NOT IN (SELECT unused_images.title FROM unused_images) '
    'GROUP BY images.id ORDER BY COUNT(*) DESC, images.id ASC')

#Get the offset of the row that follows a specified image in any of the views above
#Parameters:
# - category: Specifies the view from which to get the offset
# - image_title: The title of the image after which to get the row offset
#Return value: The resulting row offset or 0 if the image isn't found
def get_offset_after(category: Category, image_title: str) -> int:
  row = db.get().execute(
    f'SELECT row_num FROM '
      f'(SELECT image_title, ROW_NUMBER() OVER ({category.value['order']}) AS row_num '
      f'FROM {category.value['view']})'
    f'WHERE image_title = ?', (image_title,)).fetchone()

  return 0 if row is None else row[0]
