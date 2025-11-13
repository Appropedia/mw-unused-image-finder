from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  #This view allows to query for information on all revision reviews associated to a given image
  #review (if any exists)
  db.get().execute(
    'CREATE VIEW IF NOT EXISTS '
    'image_revision_reviews_view(image_id, revision_timestamp, cleanup_action_name, '
    'cleanup_reason_name) AS '
    'SELECT image_reviews.image_id, revisions.timestamp, cleanup_actions.name, '
    'cleanup_reasons.name FROM image_reviews '
    'INNER JOIN revision_reviews ON image_reviews.image_id = revision_reviews.image_id '
    'INNER JOIN revisions ON revision_reviews.revision_id = revisions.id '
    'INNER JOIN cleanup_actions ON revision_reviews.cleanup_action_id = cleanup_actions.id '
    'INNER JOIN cleanup_reasons ON revision_reviews.cleanup_reason_id = cleanup_reasons.id')

#Get all revision reviews for a given image review
def get(image_id: str) -> dict[str, dict[str, str]]:
  results = db.get().execute(
    'SELECT revision_timestamp, cleanup_action_name, cleanup_reason_name '
    'FROM image_revision_reviews_view WHERE image_id = ?', (image_id,)).fetchall()

  return {
    row[0]: {
      'cleanup_action_name': row[1],
      'cleanup_reason_name': row[2],
    } for row in results
  }
