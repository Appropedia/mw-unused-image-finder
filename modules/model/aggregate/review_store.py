import enum
from datetime import datetime
from modules.model import db
from modules.model.table import images, revisions, cleanup_actions, cleanup_reasons
from modules.model.table import image_reviews, revision_reviews

#Enumeration of operation results
class Status(enum.Enum):
  SUCCESS              = enum.auto()
  NON_EXISTENT_IMAGE   = enum.auto()
  NON_EXISTEN_REVISION = enum.auto()
  NON_EXISTENT_ACTION  = enum.auto()
  NON_EXISTENT_REASON  = enum.auto()

#Store a review by validating the existence of the required database entities and then writing to
#the relevant tables
def write(image_title: str, user_id: int, form_data: dict[str, str | dict[str, str]]) -> Status:
  with db.get() as con:
    #This is a relatively long operation that could be perturbed by many other database operations,
    #as many tables are read and then all tables related to the review process are modified. Make
    #sure this doesn't happen.
    con.execute('BEGIN EXCLUSIVE')

    #Obtain the id for the selected image
    image_id = images.read_id(image_title)
    if image_id is None:
      return Status.NON_EXISTENT_IMAGE

    #Retrieve from the database all the ids required to register every revision review
    revision_review_data = []
    for timestamp, data in form_data['revisions'].items():
      revision_id = revisions.read_id(image_id, timestamp)
      if revision_id is None:
        return Status.NON_EXISTEN_REVISION

      cleanup_action_id = cleanup_actions.read_id(data['action'])
      if cleanup_action_id is None:
        return Status.NON_EXISTENT_ACTION

      cleanup_reason_id = cleanup_reasons.read_id(data['reason'])
      if cleanup_reason_id is None:
        return Status.NON_EXISTENT_REASON

      revision_review_data.append({
        'revision_id': revision_id,
        'cleanup_action_id': cleanup_action_id,
        'cleanup_reason_id': cleanup_reason_id,
      })

    #Write the image review, register the current review author and write every revision review to
    #the database
    try:
      current_time = datetime.now()
      image_review_id = image_reviews.write(con, image_id, user_id, current_time,
                                            form_data['comments'])
      for data in revision_review_data:
        revision_reviews.write(con, image_review_id, data['revision_id'],
                               data['cleanup_action_id'], data['cleanup_reason_id'])
    except:
      con.rollback()
      raise

  return Status.SUCCESS
