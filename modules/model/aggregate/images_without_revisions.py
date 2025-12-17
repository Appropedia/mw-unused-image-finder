from modules.model import db

#Delete any image that has no revisions (used for pruning after fully synchronizing revisions)
def prune() -> None:
  with db.get() as con:
    con.execute('DELETE FROM images WHERE id NOT IN (SELECT image_id FROM revisions)')
