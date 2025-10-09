from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  #This view allows to query information for all revisions of all unused images
  db.get().execute(
    'CREATE VIEW IF NOT EXISTS '
    'unused_image_revisions_view(image_id, image_title, revision_size) AS '
    'SELECT images.id, images.title, revisions.size FROM images '
    'INNER JOIN revisions ON images.id = revisions.image_id '
    'WHERE images.title IN (SELECT unused_images.title FROM unused_images)')

#Get the title of the image that uses the largest total space including all of its revisions
def get_largest_unused(offset: int) -> str | None:
  row = db.get().execute(
    'SELECT image_title FROM unused_image_revisions_view GROUP BY image_id '
    'ORDER BY SUM(revision_size) DESC LIMIT 1 OFFSET ?', (offset,)).fetchone()

  return None if row is None else row[0]
