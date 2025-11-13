import sqlite3
from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  con = db.get()

  con.execute(
    'CREATE TABLE IF NOT EXISTS revision_reviews('
      'revision_id INTEGER PRIMARY KEY REFERENCES revisions(id) ON DELETE CASCADE, '
      'image_id INTEGER NOT NULL REFERENCES image_reviews(image_id) ON DELETE CASCADE, '
      'cleanup_action_id INTEGER NOT NULL REFERENCES cleanup_actions(id) ON DELETE RESTRICT, '
      'cleanup_reason_id INTEGER NOT NULL REFERENCES cleanup_reasons(id) ON DELETE RESTRICT, '
      'UNIQUE (revision_id, image_id))')

  #These insert and update triggers are used to make sure that no revision review exists where the
  #referenced image review and the referenced revision refer to different images
  con.execute(
    'CREATE TRIGGER IF NOT EXISTS revision_reviews_insert_check BEFORE INSERT ON revision_reviews '
    'WHEN NEW.image_id <> (SELECT image_id FROM revisions WHERE id = NEW.revision_id) '
    'BEGIN SELECT RAISE(ABORT, \'The review and revision refer to different images\'); END')

  con.execute(
    'CREATE TRIGGER IF NOT EXISTS revision_reviews_update_check BEFORE UPDATE ON revision_reviews '
    'WHEN NEW.image_id <> (SELECT image_id FROM revisions WHERE id = NEW.revision_id) '
    'BEGIN SELECT RAISE(ABORT, \'The review and revision refer to different images\'); END')

#Create a review for a given revision or update an existing one
def write(con: sqlite3.Connection, revision_id: int, image_id: int, cleanup_action_id: int,
          cleanup_reason_id) -> None:
  con.execute(
    'INSERT INTO revision_reviews (revision_id, image_id, cleanup_action_id, cleanup_reason_id) '
    'VALUES (:revision_id, :image_id, :cleanup_action_id, :cleanup_reason_id) '
    'ON CONFLICT (revision_id) DO UPDATE SET image_id = :image_id, '
    'cleanup_action_id = :cleanup_action_id, cleanup_reason_id = :cleanup_reason_id',
    { 'revision_id': revision_id, 'image_id': image_id, 'cleanup_action_id': cleanup_action_id,
      'cleanup_reason_id': cleanup_reason_id })
