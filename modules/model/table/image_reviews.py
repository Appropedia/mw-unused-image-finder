from datetime import datetime, timezone
import sqlite3
from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  db.get().execute(
    'CREATE TABLE IF NOT EXISTS image_reviews('
      'image_id INTEGER PRIMARY KEY REFERENCES images(id) ON DELETE CASCADE, '
      'last_reviewer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT, '
      'auditor_id INTEGER REFERENCES users(id) ON DELETE RESTRICT, '
      'update_time TEXT NOT NULL, '
      'approval_time TEXT, '
      'comments TEXT NOT NULL)')

#Create a review for a given image or update an existing one
def write(con: sqlite3.Connection, image_id: int, last_reviewer_id: int, comments: str) -> None:
  update_time = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')

  con.execute(
    'INSERT INTO image_reviews (image_id, last_reviewer_id, update_time, comments) '
    'VALUES (:image_id, :last_reviewer_id, :update_time, :comments) '
    'ON CONFLICT (image_id) DO UPDATE SET last_reviewer_id = :last_reviewer_id, '
    'update_time = :update_time, comments = :comments',
    { 'image_id': image_id, 'last_reviewer_id': last_reviewer_id, 'update_time': update_time,
      'comments': comments })
