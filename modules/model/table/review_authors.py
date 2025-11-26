from datetime import datetime, timezone
import sqlite3
from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  db.get().execute(
    'CREATE TABLE IF NOT EXISTS review_authors('
      'image_id INTEGER NOT NULL REFERENCES image_reviews(image_id) ON DELETE CASCADE, '
      'user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, '
      'timestamp TEXT NOT NULL, '
      'UNIQUE (image_id, user_id))')

#Register an author for a given review if not registered already
def write(con: sqlite3.Connection, image_id: int, user_id: int, timestamp: datetime) -> None:
  timestamp = timestamp.astimezone(timezone.utc)  #Make sure the timezone is UTC

  con.execute(
    'INSERT INTO review_authors (image_id, user_id, timestamp) '
    'VALUES (:image_id, :user_id, :timestamp) '
    'ON CONFLICT (image_id, user_id) DO UPDATE SET timestamp = :timestamp',
    { 'image_id': image_id,
      'user_id': user_id,
      'timestamp': timestamp.replace(microsecond=0).isoformat().replace('+00:00', 'Z') })
