from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  db.get().execute(
    'CREATE TABLE IF NOT EXISTS images('
      'id INTEGER PRIMARY KEY, '
      'title TEXT UNIQUE NOT NULL)')

#Read an existing image id, or create an image and return its id in case it doesn't exist yet
def create_read_id(title: str) -> int:
  con = db.get()

  id_ = read_id(title)
  if id_ is not None:
    return id_

  with con:
    row = con.execute(
      'INSERT INTO images (title) VALUES (?) RETURNING id', (title,)).fetchone()

  return row[0]

#Read the id of an image given its title
def read_id(title: str) -> int | None:
  row = db.get().execute('SELECT id FROM images WHERE title = ?', (title,)).fetchone()
  return None if row is None else row[0]

#Read the title of an image given its id
def read_title(id_: int) -> str | None:
  row = db.get().execute('SELECT title FROM images WHERE id = ?', (id_,)).fetchone()
  return None if row is None else row[0]

#Get image titles in a given range filtered by partial title match, ignoring the namespace portion
#(e.g. 'File:')
def get_range(limit: int, offset: int, search_term: str) -> tuple[list[str], bool]:
  #Request the titles matching the provided search term for a limited range while escaping any
  #potential wildcard character in said term, also request one additional row to confirm that more
  #rows follow
  cursor = db.get().execute(
    "SELECT title FROM images WHERE SUBSTR(title, INSTR(title, ':') + 1) LIKE ? ESCAPE ? "
    'LIMIT ? OFFSET ?',
    ('%{}%'.format(search_term.translate(str.maketrans({ '\\': r'\\',
                                                         '%':  r'\%',
                                                         '_':  r'\_' }))),
     '\\', limit + 1, offset))

  cursor.row_factory = lambda cur, row: row[0]

  #Collect all matching titles
  results = cursor.fetchmany(limit)

  #Attempt to fetch the additional row, if None then no more rows follow
  more_results = cursor.fetchone() is not None

  return results, more_results

#Delete an image given its title
def delete(title: str) -> None:
  with db.get() as con:
    con.execute('DELETE FROM images WHERE title = ?', (title,))
