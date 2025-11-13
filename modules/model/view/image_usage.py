from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  con = db.get()

  #This view allows to query for the next unused image with the largest combined size of all of its
  #revisions
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'unused_image_all_revisions_view(row_num, image_id, image_title) AS '
    'SELECT ROW_NUMBER() OVER (ORDER BY SUM(revisions.size) DESC, images.id ASC), '
    'images.id, images.title FROM images '
    'INNER JOIN revisions ON images.id = revisions.image_id '
    'WHERE images.title IN (SELECT unused_images.title FROM unused_images) '
    'GROUP BY images.id')

  #This view allows to query for the next used image with the largest combined size of all of its
  #older revisions
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'used_image_old_revisions_view(row_num, image_id, image_title) AS '
    'SELECT ROW_NUMBER() OVER (ORDER BY SUM(revision_size) DESC, image_id ASC), '
    'image_id, image_title FROM '
      '(SELECT images.id as image_id, images.title as image_title, '
      'revisions.size as revision_size, revisions.timestamp as revision_timestamp FROM images '
      'INNER JOIN revisions ON images.id = revisions.image_id '
      'WHERE images.title NOT IN (SELECT unused_images.title FROM unused_images)) '
    'WHERE revision_timestamp NOT IN '
      '(SELECT MAX(revisions.timestamp) FROM images '
      'INNER JOIN revisions ON images.id = revisions.image_id '
      'WHERE images.id = image_id GROUP BY images.id)'
    'GROUP BY image_id')

  #This view allows to query for the next used image with the largest combined size of all of its
  #revisions
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'used_image_all_revisions_view(row_num, image_id, image_title) AS '
    'SELECT ROW_NUMBER() OVER (ORDER BY SUM(revisions.size) DESC, images.id ASC), '
    'images.id, images.title FROM images '
    'INNER JOIN revisions ON images.id = revisions.image_id '
    'WHERE images.title NOT IN (SELECT unused_images.title FROM unused_images) '
    'GROUP BY images.id')

  #This view allows to query for the next used image with the largest amount of revisions
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'used_image_all_revisions_count_view(row_num, image_id, image_title) AS '
    'SELECT ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC, images.id ASC), '
    'images.id, images.title FROM images '
    'INNER JOIN revisions ON images.id = revisions.image_id '
    'WHERE images.title NOT IN (SELECT unused_images.title FROM unused_images) '
    'GROUP BY images.id')
