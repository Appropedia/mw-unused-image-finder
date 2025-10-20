import enum
from time import time
from modules.model import db
from modules.model.table import image_concessions
from modules.model.view import image_usage

#Acquire the next image available from a specified usage category on behalf of a specified user
#Parameters:
# - user_id: The user to which the image is to be conceded.
# - concession_period: How long previously conceded images are observed.
# - category: The image usage category from which to take the next image.
# - prev_title: Sets the continuation point after which the next image will be chosen.
#Return value: The title of the next image that is available, or None if unavailable.
def acquire_next(user_id: int, concession_period: int, category: image_usage.Category,
                 prev_title: str | None) -> str | None:
  #Calculate the time of the oldest concession that will be observed
  time_threshold = int(time()) - concession_period

  with db.get() as con:
    #This is a relatively long operation that could be perturbed by other acquirements, as the
    #image concessions table is modified at the very end. Make sure this doesn't happen.
    con.execute('BEGIN EXCLUSIVE')

    #If a previous image was provided, the candidate search will be offset by the position of that
    #image in the view, so that previous image including the last one are excluded
    offset = 0 if prev_title is None else image_usage.get_offset_after(category, prev_title)

    #Perform the candidate search now
    row = con.execute(
      f'SELECT image_title, image_id FROM {category.value['view']} WHERE image_id NOT IN '
        f'(SELECT image_id FROM image_concessions WHERE user_id <> ? AND timestamp > ?) '
      f'LIMIT 1 OFFSET ?', (user_id, time_threshold, offset)).fetchone()

    if row is None: return None   #No image candidate is found

    next_image_title, next_image_id = row

    #Write the concession so other users get other images during the concession period
    image_concessions.write(user_id, next_image_id)

    return next_image_title
