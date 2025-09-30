from collections.abc import Iterable
from modules.model import db

#Schema initialization function
@db.schema
def init_schema():
  db.get().execute(
    'CREATE TABLE IF NOT EXISTS unused_images('
      'title TEXT UNIQUE NOT NULL)')

#Check whether an image is in the unused images table
def exists(title: str) -> bool:
  return db.get().execute(
    'SELECT 1 FROM unused_images WHERE title = ?', (title,)).fetchone() is not None

#Create an scratch table for registering new unused images
def synchronize_begin():
  db.get().execute(
    'CREATE TEMPORARY TABLE new_unused_images('
      'title TEXT UNIQUE NOT NULL)')

#Insert a group of image titles into the scratch table
def synchronize_add_many(titles: Iterable[str]):
  with db.get() as con:
    con.executemany('INSERT INTO new_unused_images (title) VALUES (?)',
                    ((t,) for t in titles))

#Update the unused_images table using the scratch table
def synchronize_end():
  with db.get() as con:
    con.execute('DELETE FROM unused_images')
    con.execute('INSERT INTO unused_images (title) SELECT title FROM new_unused_images')
    con.execute('DROP TABLE new_unused_images')
