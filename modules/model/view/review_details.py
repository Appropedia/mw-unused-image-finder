from collections.abc import Iterator
from contextlib import closing
import sqlite3
from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  con = db.get()

  #This view allows to query for the cleanup action and cleanup reason of every revision included in
  #a particular image review
  db.get().execute(
    'CREATE VIEW IF NOT EXISTS '
    'cleanup_proposal_view(image_id, revision_timestamp, cleanup_action_name, cleanup_reason_name) '
    'AS SELECT revision_reviews.image_id, revisions.timestamp, cleanup_actions.name, '
    'cleanup_reasons.name FROM revision_reviews '
    'INNER JOIN revisions ON revision_reviews.revision_id = revisions.id '
    'INNER JOIN cleanup_actions ON revision_reviews.cleanup_action_id = cleanup_actions.id '
    'INNER JOIN cleanup_reasons ON revision_reviews.cleanup_reason_id = cleanup_reasons.id')

  #This view allows to query for the names of the authors and modification times of a particular
  #image review
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'image_review_authors_view(image_id, user_name, timestamp) AS '
    'SELECT review_authors.image_id, users.name, review_authors.timestamp FROM review_authors '
    'INNER JOIN users ON review_authors.user_id = users.id')

  #This view allows to query for information on all the reviews that satisfy a particular set of
  #filters
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'review_filter_view(image_id, image_review_update_time, image_review_comments, image_title, '
    'auditor_user_name, author_user_name, cleanup_action_name, cleanup_reason_name) AS '
    'SELECT image_reviews.image_id, image_reviews.update_time, image_reviews.comments, '
    'images.title, auditors.name, authors.name, cleanup_actions.name, cleanup_reasons.name '
    'FROM image_reviews '
    'LEFT JOIN images ON image_reviews.image_id = images.id '
    'LEFT JOIN users AS auditors ON image_reviews.auditor_id = auditors.id '
    'LEFT JOIN review_authors ON image_reviews.image_id = review_authors.image_id '
    'LEFT JOIN users AS authors ON review_authors.user_id = authors.id '
    'LEFT JOIN revision_reviews ON image_reviews.image_id = revision_reviews.image_id '
    'LEFT JOIN cleanup_actions ON revision_reviews.cleanup_action_id = cleanup_actions.id '
    'LEFT JOIN cleanup_reasons ON revision_reviews.cleanup_reason_id = cleanup_reasons.id')

#Get all information stored for a given given image review
def get_single(image_id: int) -> dict[str, str | dict[str, dict[str, str]]]:
  con = db.get()

  #Get the review comments
  comments_row = con.execute(
    'SELECT comments FROM image_reviews WHERE image_id = ?', (image_id,)).fetchone()

  comments = '' if comments_row is None else comments_row[0]

  #Get the cleanup action and cleanup reason of every revision included in the review
  cleanup_proposal_cursor = con.execute(
    'SELECT revision_timestamp, cleanup_action_name, cleanup_reason_name '
    'FROM cleanup_proposal_view WHERE image_id = ?', (image_id,)).fetchall()

  return {
    'comments': comments,
    'cleanup_proposal': {
      row[0]: {
        'cleanup_action_name': row[1],
        'cleanup_reason_name': row[2],
      } for row in cleanup_proposal_cursor
    },
  }

#Formulate a couple of SQL string lists that can be used for filtering review data
#Parameters:
# - filter_params: A dictionary containing filter parameters
#Return values:
# - filter_conditions: A list of strings containing sql conditions to be added to the WHERE clause
# - filter_values: A list containing values to be added to the query as positional parameters
def _sql_filter_params(filter_params: dict[str, str]) -> tuple[list[str], list[any]]:
  filter_conditions = []
  filter_values = []
  for param, value in filter_params.items():
    match param:
      case 'review_author':
        #For direct string matches, use an equality expression and apend the input value as is
        filter_conditions.append('author_user_name = ?')
        filter_values.append(value)
      case 'cleanup_action':
        filter_conditions.append('cleanup_action_name = ?')
        filter_values.append(value)
      case 'cleanup_reason':
        filter_conditions.append('cleanup_reason_name = ?')
        filter_values.append(value)
      case 'image_title':
        #For text searches, use a LIKE/ESCAPE expression with a pattern that matches any part of the
        #string, escaping any potential wildcard character in the input string
        filter_conditions.append('image_title LIKE ? ESCAPE ?')
        filter_values.append('%{}%'.format(value.translate(str.maketrans({ '\\': r'\\',
                                                                           '%':  r'\%',
                                                                           '_':  r'\_' }))))
        filter_values.append('\\')
      case _ as invalid_param:
        raise ValueError(f'Invalid filter parameter name: {invalid_param}')

  return filter_conditions, filter_values

#Get information about the authors of a given review
def _get_review_authors(con: sqlite3.Connection, image_id: int) -> list[dict[str, str]]:
  cursor = con.execute(
    'SELECT user_name, timestamp FROM image_review_authors_view WHERE image_id = ? '
    'ORDER BY timestamp ASC', (image_id,))

  cursor.row_factory = lambda cur, row: { 'user_name': row[0], 'timestamp': row[1] }

  return cursor.fetchall()

#Get the cleanup proposal information for each of the image revisions covered in an image review
def _get_cleanup_proposal(con: sqlite3.Connection, image_id: int) -> list[dict[str, str]]:
  cursor = con.execute(
    'SELECT revision_timestamp, cleanup_action_name, cleanup_reason_name '
    'FROM cleanup_proposal_view WHERE image_id = ? ORDER BY revision_timestamp DESC', (image_id,))

  cursor.row_factory = lambda cur, row: { 'timestamp': row[0], 'action': row[1], 'reason': row[2] }

  return cursor.fetchall()

#Return information about all reviews in a given range
def get_range(limit: int, offset: int, filter_params: dict[str, str]) -> \
              tuple[list[dict[str, str | list[dict[str, str]]]], bool]:
  con = db.get()

  #Populate the SQL filter conditions and values with data from the provided filter parameters
  filter_conditions, filter_values = _sql_filter_params(filter_params)

  #Request the reviews matching the provided filters for a limited range, request one additional row
  #to confirm that more rows follow
  cursor = con.execute(
    'SELECT DISTINCT image_id, image_title, image_review_update_time, image_review_comments '
    'FROM review_filter_view ' +
    (f'WHERE {' AND '.join(filter_conditions)} ' if filter_conditions else '') +
    'ORDER BY image_review_update_time ASC, image_id ASC LIMIT ? OFFSET ?',
    (*filter_values, limit + 1, offset))

  cursor.row_factory = lambda cur, row: { 'image_title': row[1],
                                          'update_time': row[2],
                                          'comments': row[3],
                                          'authors': _get_review_authors(con, row[0]),
                                          'cleanup_proposal': _get_cleanup_proposal(con, row[0]) }

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
  filter_conditions, filter_values = _sql_filter_params(filter_params)

  #This function is intended to be called from outside a request context as it can be passed as a
  #generator function to Flask's Request function, so an independent database connection is used
  with closing(db.contextless_get()) as con:
    continue_conditions = []
    continue_values = []
    while True:
      all_conditions = filter_conditions + continue_conditions

      #Request the reviews matching the current filters for the next block
      cursor = con.execute(
        'SELECT DISTINCT image_id, image_title, image_review_update_time, image_review_comments '
        'FROM review_filter_view ' +
        (f'WHERE {' AND '.join(all_conditions)} ' if all_conditions else '') +
        'ORDER BY image_review_update_time ASC, image_id ASC LIMIT ?',
        filter_values + continue_values + [BLOCK_LENGTH])

      cursor.row_factory = lambda cur, row: (
        row[0], { 'image_title': row[1],
                  'update_time': row[2],
                  'comments': row[3],
                  'authors': _get_review_authors(con, row[0]),
                  'cleanup_proposal': _get_cleanup_proposal(con, row[0]) })

      #Collect all data pertaining to matching reviews
      #Note: The for loop is used unconventionally to have the last iteration values remain in scope
      results = []
      for image_id, review_details in cursor:
        results.append(review_details)

      #Yield blocks with up to BLOCK_LENGTH rows at a time as lists of dictionaries
      yield results

      #Finish the process if less rows than requested were returned
      if len(results) < BLOCK_LENGTH:
        break

      #Update the continuation variables in case there are more blocks
      continue_conditions = ['(image_review_update_time, image_id) > (?, ?)']
      continue_values = [review_details['update_time'], image_id]
