from datetime import datetime, timezone
import sqlite3
from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  db.get().execute(
    'CREATE TABLE IF NOT EXISTS image_reviews('
      'image_id INTEGER PRIMARY KEY REFERENCES images(id) ON DELETE CASCADE, '
      'auditor_id INTEGER REFERENCES users(id) ON DELETE RESTRICT, '
      'update_time TEXT NOT NULL, '
      'approval_time TEXT, '
      'comments TEXT NOT NULL)')

#Create a review for a given image or update an existing one
def write(con: sqlite3.Connection, image_id: int, update_time: datetime, comments: str) -> None:
  update_time = update_time.astimezone(timezone.utc)  #Make sure the timezone is UTC

  con.execute(
    'INSERT INTO image_reviews (image_id, update_time, comments) '
    'VALUES (:image_id, :update_time, :comments) '
    'ON CONFLICT (image_id) DO UPDATE SET update_time = :update_time, comments = :comments',
    { 'image_id': image_id,
      'update_time': update_time.replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
      'comments': comments })
