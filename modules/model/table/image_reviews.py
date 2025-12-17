from datetime import datetime, timezone
import sqlite3
from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  db.get().execute(
    'CREATE TABLE IF NOT EXISTS image_reviews('
      'id INTEGER PRIMARY KEY, '
      'image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE, '
      'user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, '
      'timestamp TEXT NOT NULL, '
      'bot_timestamp TEXT, '
      'comments TEXT NOT NULL, '
      'UNIQUE (image_id, user_id))')

#Create a review for a given image or update an existing one, returning its id
def write(con: sqlite3.Connection, image_id: int, user_id: int, timestamp: datetime,
          comments: str) -> None:
  timestamp = timestamp.astimezone(timezone.utc)  #Make sure the timezone is UTC

  return con.execute(
    'INSERT INTO image_reviews (image_id, user_id, timestamp, comments) '
    'VALUES (:image_id, :user_id, :timestamp, :comments) '
    'ON CONFLICT (image_id, user_id) DO UPDATE SET timestamp = :timestamp, comments = :comments '
    'RETURNING id',
    { 'image_id': image_id,
      'user_id': user_id,
      'timestamp': timestamp.replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
      'comments': comments }).fetchone()[0]
