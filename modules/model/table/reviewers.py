import sqlite3
from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  db.get().execute(
    'CREATE TABLE IF NOT EXISTS reviewers('
      'image_id INTEGER NOT NULL REFERENCES image_reviews(image_id) ON DELETE CASCADE, '
      'user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, '
      'UNIQUE (image_id, user_id))')

#Register a reviewer for a given review if not registered already
def write(con: sqlite3.Connection, image_id: int, user_id: int):
  con.execute(
    'INSERT INTO reviewers (image_id, user_id) VALUES (?, ?) '
    'ON CONFLICT (image_id, user_id) DO NOTHING', (image_id, user_id))
