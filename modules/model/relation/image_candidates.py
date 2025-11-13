import enum
from time import time
from modules.model import db
from modules.model.table import image_concessions

#Enumeration of available image usage categories
class Category(enum.Enum):
  unused_img_all_rev     = 'unused_image_all_revisions_view'
  used_img_old_rev       = 'used_image_old_revisions_view'
  used_img_all_rev       = 'used_image_all_revisions_view'
  used_img_all_rev_count = 'used_image_all_revisions_count_view'

#Acquire the next image available from a specified usage category on behalf of a specified user
#Parameters:
# - user_id: The user to which the image is to be conceded.
# - concession_period: How long previously conceded images are observed.
# - category: The image usage category from which to take the next image.
# - prev_title: Sets the continuation point after which the next image will be chosen.
#Return value: The title of the next image that is available, or None if unavailable.
def acquire_next(user_id: int, concession_period: int, category: Category,
                 prev_title: str | None) -> str | None:
  #Calculate the time of the oldest concession that will be observed
  time_threshold = int(time()) - concession_period

  with db.get() as con:
    #This operation could be perturbed by other acquirements, as the image concessions table is
    #modified after reading from many tables, including it. Make sure this doesn't happen.
    con.execute('BEGIN EXCLUSIVE')

    #Perform the candidate search now. The filter conditions are as follows:
    # - The image image must be after the continuation point (higher row number)
    # - The image has not been recently conceded to another user
    # - The image is missing a review for at least one of its revisions
    row = con.execute(
      f'SELECT image_title, image_id FROM {category.value} '
      f'WHERE row_num > COALESCE('
        f'(SELECT row_num FROM {category.value} WHERE image_title = ?), 0) '
      f'AND image_id NOT IN '
        f'(SELECT image_id FROM image_concessions WHERE user_id <> ? AND timestamp > ?) '
      f'AND image_id IN '
        f'(SELECT revisions.image_id FROM revisions '
        f'LEFT JOIN revision_reviews ON revisions.id = revision_reviews.revision_id '
        f'WHERE revision_reviews.revision_id IS NULL) '
      f'ORDER BY row_num ASC LIMIT 1', (prev_title, user_id, time_threshold)).fetchone()

    if row is None:
      #If the candidate search did not return any result (the pool is shallow), retry ignoring
      #previous concessions so that the last images are forced to appear, even if conceded to
      #another user
      row = con.execute(
        f'SELECT image_title, image_id FROM {category.value} '
        f'WHERE row_num > COALESCE('
          f'(SELECT row_num FROM {category.value} WHERE image_title = ?), 0) '
        f'AND image_id IN '
          f'(SELECT revisions.image_id FROM revisions '
          f'LEFT JOIN revision_reviews ON revisions.id = revision_reviews.revision_id '
          f'WHERE revision_reviews.revision_id IS NULL) '
        f'ORDER BY row_num ASC LIMIT 1', (prev_title,)).fetchone()

      #If available images run out right before a user requests the next one, this last search may
      #not return anything. In that case restarting the dealing process (requesting an image with no
      #previous title) will always return the last unreviewed images, regardless of concession
      #status.

      if row is None: return None   #No image candidate is found

    next_image_title, next_image_id = row

    #Write the concession so other users get other images during the concession period
    image_concessions.write(user_id, next_image_id)

    return next_image_title
