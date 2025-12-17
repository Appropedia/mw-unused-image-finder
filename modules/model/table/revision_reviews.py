import sqlite3
from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  con = db.get()

  con.execute(
    'CREATE TABLE IF NOT EXISTS revision_reviews('
      'image_review_id INTEGER NOT NULL REFERENCES image_reviews(id) ON DELETE CASCADE, '
      'revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE, '
      'cleanup_action_id INTEGER NOT NULL REFERENCES cleanup_actions(id) ON DELETE CASCADE, '
      'cleanup_reason_id INTEGER NOT NULL REFERENCES cleanup_reasons(id) ON DELETE CASCADE, '
      'UNIQUE (image_review_id, revision_id))')

  #These insert and update triggers are used to make sure that no revision review exists where the
  #referenced image review and the referenced revision refer to different images
  con.execute(
    'CREATE TRIGGER IF NOT EXISTS revision_reviews_insert_check BEFORE INSERT ON revision_reviews '
    'WHEN (SELECT image_id FROM image_reviews WHERE id = NEW.image_review_id) <> '
         '(SELECT image_id FROM revisions WHERE id = NEW.revision_id) '
    'BEGIN SELECT RAISE(ABORT, \'The image review and revision refer to different images\'); END')

  con.execute(
    'CREATE TRIGGER IF NOT EXISTS revision_reviews_update_check BEFORE UPDATE ON revision_reviews '
    'WHEN (SELECT image_id FROM image_reviews WHERE id = NEW.image_review_id) <> '
         '(SELECT image_id FROM revisions WHERE id = NEW.revision_id) '
    'BEGIN SELECT RAISE(ABORT, \'The image review and revision refer to different images\'); END')

#Create a review for a given revision or update an existing one
def write(con: sqlite3.Connection, image_review_id: int, revision_id: int, cleanup_action_id: int,
          cleanup_reason_id) -> None:
  con.execute(
    'INSERT INTO revision_reviews (image_review_id, revision_id, cleanup_action_id, '
                                  'cleanup_reason_id) '
    'VALUES (:image_review_id, :revision_id, :cleanup_action_id, :cleanup_reason_id) '
    'ON CONFLICT (image_review_id, revision_id) '
    'DO UPDATE SET cleanup_action_id = :cleanup_action_id, cleanup_reason_id = :cleanup_reason_id',
    { 'image_review_id': image_review_id, 'revision_id': revision_id,
      'cleanup_action_id': cleanup_action_id, 'cleanup_reason_id': cleanup_reason_id })
