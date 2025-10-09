from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  #This view allows to query information for all revisions of all images
  db.get().execute(
    'CREATE VIEW IF NOT EXISTS '
    'image_revisions_view(image_id, image_title, revision_id, revision_timestamp, revision_size) '
    'AS SELECT images.id, images.title, revisions.id, revisions.timestamp, revisions.size FROM '
    'images INNER JOIN revisions ON images.id = revisions.image_id')

#Get summarized information about a specific image
def get_image_summary(image_title: str) -> tuple[int, str, int, int, int] |\
                                           tuple[None, None, None, None, None]:
  row = db.get().execute(
    'SELECT image_id, MAX(revision_timestamp), MAX(revision_size), SUM(revision_size), COUNT(*) '
    'FROM image_revisions_view WHERE image_title = ? GROUP BY image_id', (image_title,)).fetchone()

  return (None,) * 5 if row is None else row

#Get information about a specific revision
def get_revision_info(revision_id: int) -> tuple[int, str, str]:
  return db.get().execute(
    'SELECT image_id, image_title, revision_timestamp FROM image_revisions_view '
    'WHERE revision_id = ? LIMIT 1', (revision_id,)).fetchone()
