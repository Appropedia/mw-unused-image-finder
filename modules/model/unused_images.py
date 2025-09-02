from collections.abc import Iterable
from modules.model import db

#Schema initialization function
@db.schema
def init_schema():
  db.get().execute(
    'CREATE TABLE IF NOT EXISTS unused_images('
      'title STRING UNIQUE NOT NULL)')

#Create an scratch table for registering new unused images
def create_temp_table():
  db.get().execute(
    'CREATE TEMPORARY TABLE new_unused_images('
      'title STRING UNIQUE NOT NULL)')

#Insert a group of image titles into the scratch table
def insert_into_temp_table(titles: Iterable[str]):
  con = db.get()
  con.executemany('INSERT INTO new_unused_images(title) VALUES (?)',
                  ((t,) for t in titles))
  con.commit()

#Update the unused_images table using the scratch table
def update_from_temp_table():
  con = db.get()
  con.execute('BEGIN TRANSACTION')
  con.execute('DELETE FROM unused_images')
  con.execute('INSERT INTO unused_images(title) SELECT title FROM new_unused_images')
  con.commit()
