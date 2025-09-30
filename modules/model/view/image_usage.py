from modules.model import db

#Schema initialization function
@db.schema
def init_schema():
  con = db.get()

  #This view allows to query information for all revisions of all unused images
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'unused_image_revisions_view(image_id, image_title, revision_timestamp, revision_size) AS '
    'SELECT images.id, images.title, revisions.timestamp, revisions.size FROM images '
    'INNER JOIN revisions ON images.id = revisions.image_id '
    'WHERE images.title IN (SELECT unused_images.title FROM unused_images)')

#Get the title of the image that uses the largest total space including all of its revisions
def largest_unused(offset: int) -> str:
  row = db.get().execute(
    'SELECT image_title FROM unused_image_revisions_view WHERE revision_size IS NOT NULL '
    'GROUP BY image_id ORDER BY SUM(revision_size) DESC LIMIT 1 OFFSET ?', (offset,)).fetchone()

  return row[0] if row is not None else None

#Read summarized information about a given image
def read(image_title: int) -> tuple[int, str, int, int, int]:
  row = db.get().execute(
    'SELECT image_id, MAX(revision_timestamp), MAX(revision_size), SUM(revision_size), COUNT(*) '
    'FROM unused_image_revisions_view WHERE image_title = ? GROUP BY image_id',
    (image_title,)).fetchone()

  return row if row is not None else (None,) * 5
