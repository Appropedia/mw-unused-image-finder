from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  con = db.get()

  #This view serves as the base for all views below, allowing to query for files that are pending a
  #review for at least one of their revisions
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'unreviewed_images_view(image_id, image_title, revision_timestamp, revision_size) AS '
    'SELECT images.id, images.title, revisions.timestamp, revisions.size FROM images '
    'INNER JOIN revisions ON images.id = revisions.image_id '
    'WHERE images.id IN '
      '(SELECT revisions.image_id FROM revisions '
      'LEFT JOIN revision_reviews ON revisions.id = revision_reviews.revision_id '
      'WHERE revision_reviews.revision_id IS NULL)')

  #This view allows to query for the next unused image with the largest combined size of all of its
  #revisions
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'unreviewed_unused_images_by_size_of_all_revs_view(row_num, image_id, image_title) AS '
    'SELECT ROW_NUMBER() OVER (ORDER BY SUM(revision_size) DESC, image_id ASC), '
    'image_id, image_title FROM unreviewed_images_view '
    'WHERE image_title IN (SELECT title FROM unused_images) '
    'GROUP BY image_id')

  #This view allows to query for the next used image with the largest combined size of all of its
  #older revisions
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'unreviewed_used_images_by_size_of_old_revs_view(row_num, image_id, image_title) AS '
    'SELECT ROW_NUMBER() OVER (ORDER BY SUM(revision_size) DESC, image_id ASC), '
    'image_id, image_title FROM unreviewed_images_view '
    'WHERE image_title NOT IN (SELECT title FROM unused_images) '
    'AND revision_timestamp < '
      '(SELECT MAX(timestamp) FROM revisions WHERE image_id = unreviewed_images_view.image_id)'
    'GROUP BY image_id')

  #This view allows to query for the next used image with the largest combined size of all of its
  #revisions
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'unreviewed_used_images_by_size_of_all_revs_view(row_num, image_id, image_title) AS '
    'SELECT ROW_NUMBER() OVER (ORDER BY SUM(revision_size) DESC, image_id ASC), '
    'image_id, image_title FROM unreviewed_images_view '
    'WHERE image_title NOT IN (SELECT title FROM unused_images) '
    'GROUP BY image_id')

  #This view allows to query for the next used image with the largest amount of revisions
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'unreviewed_used_images_by_count_of_all_revs_view(row_num, image_id, image_title) AS '
    'SELECT ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC, image_id ASC), '
    'image_id, image_title FROM unreviewed_images_view '
    'WHERE image_title NOT IN (SELECT title FROM unused_images) '
    'GROUP BY image_id')

#Get the total count of unreviewed images in all categories
def get_unreviewed_image_totals():
  cursor = db.get().execute(
    'SELECT '
      '(SELECT COUNT(*) FROM unreviewed_unused_images_by_size_of_all_revs_view), '
      '(SELECT COUNT(*) FROM unreviewed_used_images_by_size_of_old_revs_view), '
      '(SELECT COUNT(*) FROM unreviewed_used_images_by_size_of_all_revs_view)')

  #Note: The view called unreviewed_used_images_by_size_of_all_revs_view refers to the exact same
  #set as unreviewed_used_images_by_count_of_all_revs_view, with the only difference being their
  #ordering scheme. Therefore only the count of one of the sets is calculated.

  cursor.row_factory = lambda cur, row: {
    'unreviewed_unused_images_count': row[0],
    'unreviewed_used_images_with_old_revisions_count': row[1],
    'unreviewed_used_images_count': row[2],
  }

  return cursor.fetchone()
