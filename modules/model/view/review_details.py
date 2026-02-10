from collections.abc import Iterator
from contextlib import closing
import sqlite3
from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  con = db.get()

  #This view allows to query for summarized information about every review of a given image
  db.get().execute(
    'CREATE VIEW IF NOT EXISTS '
    'review_summary_view(image_review_timestamp, image_title, user_name) AS '
    'SELECT image_reviews.timestamp, images.title, users.name FROM image_reviews '
    'INNER JOIN images ON image_reviews.image_id = images.id '
    'INNER JOIN users ON image_reviews.user_id = users.id')

  #This view allows to query for the cleanup action and cleanup reason of every revision included in
  #a particular image review
  db.get().execute(
    'CREATE VIEW IF NOT EXISTS '
    'cleanup_proposal_view(image_review_id, revision_timestamp, cleanup_action_name, '
    'cleanup_reason_name) AS '
    'SELECT revision_reviews.image_review_id, revisions.timestamp, cleanup_actions.name, '
    'cleanup_reasons.name FROM revision_reviews '
    'INNER JOIN revisions ON revision_reviews.revision_id = revisions.id '
    'INNER JOIN cleanup_actions ON revision_reviews.cleanup_action_id = cleanup_actions.id '
    'INNER JOIN cleanup_reasons ON revision_reviews.cleanup_reason_id = cleanup_reasons.id')

  #This view allows to query for information on all the reviews that satisfy a particular set of
  #filters
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'review_filter_view(image_review_id, image_id, image_review_timestamp, image_review_comments, '
    'image_title, user_name, cleanup_action_name, cleanup_reason_name) AS '
    'SELECT image_reviews.id, image_reviews.image_id, image_reviews.timestamp, '
    'image_reviews.comments, images.title, users.name, cleanup_actions.name, cleanup_reasons.name '
    'FROM image_reviews '
    'LEFT JOIN images ON image_reviews.image_id = images.id '
    'LEFT JOIN users ON image_reviews.user_id = users.id '
    'LEFT JOIN revision_reviews ON image_reviews.id = revision_reviews.image_review_id '
    'LEFT JOIN cleanup_actions ON revision_reviews.cleanup_action_id = cleanup_actions.id '
    'LEFT JOIN cleanup_reasons ON revision_reviews.cleanup_reason_id = cleanup_reasons.id')

  #This view allows to query for information on reviews that are pending synchronization by the
  #mediawiki bot component
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'review_pending_bot_sync_view(image_review_id, image_review_timestamp, image_review_comments, '
    'image_title, user_name) AS '
    'SELECT image_reviews.id, image_reviews.timestamp, image_reviews.comments, images.title, '
    'users.name FROM image_reviews '
    'INNER JOIN images ON image_reviews.image_id = images.id '
    'INNER JOIN users ON image_reviews.user_id = users.id '
    'INNER JOIN (SELECT id AS ordered_image_review_id, '
      'ROW_NUMBER() OVER (PARTITION BY image_id ORDER BY timestamp DESC, id DESC) AS row_num '
      'FROM image_reviews) ON image_reviews.id = ordered_image_review_id AND row_num = 1 '
    'WHERE bot_timestamp IS NULL OR bot_timestamp < timestamp')
  #Note: The self join filters the newest review in the case of images with multiple user reviews

#Check whether an image has been reviewed yet
def exists(image_title: str) -> bool:
  return bool(db.get().execute(
    'SELECT EXISTS (SELECT 1 FROM review_summary_view WHERE image_title = ?)',
    (image_title,)).fetchone()[0])

#Get the author name of every review of a given image
def get_authors(image_title: str) -> list[str]:
  cursor = db.get().execute(
    'SELECT user_name FROM review_summary_view WHERE image_title = ?', (image_title,))

  cursor.row_factory = lambda cur, row: row[0]

  return cursor.fetchall()

#Get summarized information about every review of a given image
def get_summary(image_title: str) -> list[dict[str, str]]:
  cursor = db.get().execute(
    'SELECT image_review_timestamp, user_name FROM review_summary_view WHERE image_title = ? ',
    (image_title,))

  cursor.row_factory = lambda cur, row: { 'timestamp': row[0], 'user_name': row[1] }

  return cursor.fetchall()

#Get the cleanup proposal information with the names of the cleanup actions and cleanup reasons for
#each of the image revisions covered in an image review
def get_cleanup_proposal(image_review_id: int) -> list[dict[str, int | str]]:
  cursor = db.get().execute(
    'SELECT revision_timestamp, cleanup_action_name, cleanup_reason_name '
    'FROM cleanup_proposal_view WHERE image_review_id = ? ORDER BY revision_timestamp DESC',
    (image_review_id,))

  cursor.row_factory = lambda cur, row: { 'revision_timestamp': row[0],
                                          'cleanup_action_name': row[1],
                                          'cleanup_reason_name': row[2] }

  return cursor.fetchall()

#This is an special version of the function above that takes a separate sqlite3 connection and
#returns data with shortened field names for JSON generation
def _get_cleanup_proposal_special(con: sqlite3.Connection,
                                  image_review_id: int) -> list[dict[str, str]]:
  cursor = con.execute(
    'SELECT revision_timestamp, cleanup_action_name, cleanup_reason_name '
    'FROM cleanup_proposal_view WHERE image_review_id = ? ORDER BY revision_timestamp DESC',
    (image_review_id,))

  cursor.row_factory = lambda cur, row: { 'timestamp': row[0], 'action': row[1], 'reason': row[2] }

  return cursor.fetchall()

#Get all information stored for a given image review
def get_single(image_id: int, user_id: int) -> dict[str, str | dict[str, dict[str, str]]]:
  con = db.get()

  #Get the review id and comments
  row = con.execute(
    'SELECT id, comments FROM image_reviews WHERE image_id = ? AND user_id = ?',
    (image_id, user_id)).fetchone()

  if row is None:
    raise ValueError('Requested review does not exist')

  image_review_id, comments = row

  #Get the cleanup action and cleanup reason of every revision included in the review
  return {
    'comments': comments,
    'cleanup_proposal': {
      row['revision_timestamp']: {
        'cleanup_action_name': row['cleanup_action_name'],
        'cleanup_reason_name': row['cleanup_reason_name'],
      } for row in get_cleanup_proposal(image_review_id)
    },
  }

#Formulate a group of SQL string lists that can be used for filtering review data
#Parameters:
# - filter_params: A dictionary containing filter parameters
#Return values:
# - filter_joins: A list of strings containing sql statements to be added as JOIN clauses
# - filter_conditions: A list of strings containing sql conditions to be added to the WHERE clause
# - filter_values: A list containing values to be added to the query as positional parameters
def _sql_filter_params(filter_params: dict[str, str]) -> tuple[list[str], list[str], list[any]]:
  filter_joins = []
  filter_conditions = []
  filter_values = []
  for param, value in filter_params.items():
    match param:
      case 'review_author':
        #For direct string matches, use an equality expression and apend the input value as is
        filter_conditions.append('user_name = ?')
        filter_values.append(value)
      case 'cleanup_action':
        filter_conditions.append('cleanup_action_name = ?')
        filter_values.append(value)
      case 'cleanup_reason':
        filter_conditions.append('cleanup_reason_name = ?')
        filter_values.append(value)
      case 'image_title':
        #For text searches, use a LIKE/ESCAPE expression with a pattern that matches any part of the
        #string after the namespace (e.g. 'File:'), while escaping any potential wildcard character
        #in the input string
        filter_conditions.append("SUBSTR(image_title, INSTR(image_title, ':') + 1) LIKE ? ESCAPE ?")
        filter_values.append('%{}%'.format(value.translate(str.maketrans({ '\\': r'\\',
                                                                           '%':  r'\%',
                                                                           '_':  r'\_' }))))
        filter_values.append('\\')
      case 'newest_only':
        #Filter to get the newest review of each image by performing an inner join
        filter_joins.append(
          'INNER JOIN (SELECT id AS ordered_image_review_id, '
          'ROW_NUMBER() OVER (PARTITION BY image_id ORDER BY timestamp DESC, id DESC) AS row_num '
          'FROM image_reviews) ON image_review_id = ordered_image_review_id AND row_num = 1')
        #Note: In the extremely rare case of a tie between two reviews sharing the same timestamp,
        #the one with the largest image_review_id will be chosen
      case _ as invalid_param:
        raise ValueError(f'Invalid filter parameter name: {invalid_param}')

  return filter_joins, filter_conditions, filter_values

#Return information about all reviews in a given range
def get_range(limit: int, offset: int, filter_params: dict[str, str]) -> \
              tuple[list[dict[str, str | list[dict[str, str]]]], bool]:
  con = db.get()

  #Populate the SQL filter conditions and values with data from the provided filter parameters
  filter_joins, filter_conditions, filter_values = _sql_filter_params(filter_params)

  #Request the reviews matching the provided filters for a limited range, request one additional row
  #to confirm that more rows follow
  cursor = con.execute(
    'SELECT DISTINCT image_review_id, image_title, image_review_timestamp, image_review_comments, '
    'user_name FROM review_filter_view ' +
    (f'{' '.join(filter_joins)} ' if filter_joins else '') +
    (f'WHERE {' AND '.join(filter_conditions)} ' if filter_conditions else '') +
    'ORDER BY MIN(image_review_timestamp) OVER (PARTITION BY image_id) ASC, image_id ASC, '
    'image_review_timestamp ASC, image_review_id ASC LIMIT ? OFFSET ?',
    (*filter_values, limit + 1, offset))

  #Note: Ordering is done by the following criteria (in order):
  # - Reviews are grouped/partitioned by image id, with the oldest review stablishing the position
  #   of the entire group
  # - In case two groups are tied by the oldest review, they're untied using the same image id by
  #   which they were partitioned - This way tied groups don't get mixed
  # - Within the same group, reviews are ordered in ascending time order
  # - As a final untie, images are sorted by image review id, which is unique

  cursor.row_factory = lambda cur, row: {
    'image_title': row[1],
    'timestamp': row[2],
    'comments': row[3],
    'author': row[4],
    'cleanup_proposal': _get_cleanup_proposal_special(con, row[0])
  }

  #Collect all data pertaining to matching reviews
  results = cursor.fetchmany(limit)

  #Attempt to fetch the additional row, if None then no more rows follow
  more_results = cursor.fetchone() is not None

  return results, more_results

#Create an iterator object that returns information about all reviews
def get_bulk(filter_params: dict[str, str]) -> \
             Iterator[list[dict[str, str | list[dict[str, str]]]]]:
  #Amount of reviews requested at a time
  BLOCK_LENGTH = 100

  #Populate the SQL filter conditions and values with data from the provided filter parameters
  filter_joins, filter_conditions, filter_values = _sql_filter_params(filter_params)

  #This function is intended to be called from outside a request context as it can be passed as a
  #generator function to Flask's Request function, so an independent database connection is used
  with closing(db.contextless_get()) as con:
    continue_conditions = []
    continue_values = []
    while True:
      all_conditions = filter_conditions + continue_conditions

      #Request the reviews matching the current filters for the next block
      cursor = con.execute(
        'SELECT DISTINCT image_review_id, image_title, image_review_timestamp, '
        'image_review_comments, user_name FROM review_filter_view ' +
        (f'{' '.join(filter_joins)} ' if filter_joins else '') +
        (f'WHERE {' AND '.join(all_conditions)} ' if all_conditions else '') +
        'ORDER BY MIN(image_review_timestamp) OVER (PARTITION BY image_id) ASC, image_id ASC, '
        'image_review_timestamp ASC, image_review_id ASC LIMIT ?',
        filter_values + continue_values + [BLOCK_LENGTH])

      cursor.row_factory = lambda cur, row: (
        row[0], { 'image_title': row[1],
                  'timestamp': row[2],
                  'comments': row[3],
                  'author': row[4],
                  'cleanup_proposal': _get_cleanup_proposal_special(con, row[0]) })

      #Collect all data pertaining to matching reviews
      #Note: The for loop is used unconventionally to have the last iteration values remain in scope
      results = []
      for image_review_id, review_details in cursor:
        results.append(review_details)

      #Yield blocks with up to BLOCK_LENGTH rows at a time as lists of dictionaries
      yield results

      #Finish the process if less rows than requested were returned
      if len(results) < BLOCK_LENGTH:
        break

      #Update the continuation variables in case there are more blocks
      continue_conditions = ['(image_review_timestamp, image_review_id) > (?, ?)']
      continue_values = [review_details['timestamp'], image_review_id]

#Create an iterator object that returns data about image reviews that are pending synchronization by
#the mediawiki bot component
def get_pending_sync_reviews() -> Iterator[dict[str, int | str]]:
  con = db.get()

  last_image_review_id = -1
  while True:
    #Request the data for the next review
    cursor = con.execute(
      'SELECT image_review_id, image_review_timestamp, image_review_comments, image_title, '
      'user_name FROM review_pending_bot_sync_view WHERE image_review_id > ? '
      'ORDER BY image_review_id LIMIT 1',
      (last_image_review_id,))

    cursor.row_factory = lambda cur, row: { 'id': row[0],
                                            'timestamp': row[1],
                                            'comments': row[2],
                                            'image_title': row[3],
                                            'author': row[4] }

    row = cursor.fetchone()

    #Yield reviews one by one until None is returned
    if row is None: break

    yield row

    #Update the continuation variable in case there's more reviews
    last_image_review_id = row['id']
