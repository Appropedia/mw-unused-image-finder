from time import time
from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  db.get().execute(
    'CREATE TABLE IF NOT EXISTS image_concessions('
      'user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, '
      'image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE, '
      'timestamp INTEGER NOT NULL, '
      'UNIQUE(image_id), '
      'UNIQUE(user_id))')

#Create a new image concession for a given user or update an existing one
def write(user_id: int, image_id: int) -> None:
  with db.get() as con:
    con.execute(
      'INSERT INTO image_concessions (user_id, image_id, timestamp) '
      'VALUES (:user_id, :image_id, :timestamp) '
      'ON CONFLICT (user_id) DO UPDATE SET image_id = :image_id, timestamp = :timestamp',
      { 'user_id': user_id, 'image_id': image_id, 'timestamp': int(time()) })
