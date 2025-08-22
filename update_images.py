#!/usr/bin/env -S sh -c 'cd $(dirname $0); python/bin/python -m $(basename ${0%.py}) $@'

from datetime import datetime
from modules.common import config
from modules.model import db
from modules.model import images
from modules.model import revisions
from modules.mediawiki import api_client

config.load('config.toml')
db.go_without_flask()

#Convert an ISO 8601 timestamp string into a unix timestamp
def iso_to_unix(iso: str) -> int:
  return int(datetime.fromisoformat(iso).timestamp())

#Create a new image index and store it in the image and revision tables
def create_image_index():
  print ('Downloading initial image indexes...')

  query_params = {'action': 'query', 'generator': 'allimages', 'gailimit': 'max',
                  'prop': 'imageinfo', 'iiprop': 'timestamp|url', 'iilimit': 'max'}

  img_count = 0
  rev_count = 0

  #Query the mediawiki server and process each parsed JSON block
  for result in api_client.query(query_params):
    for img in result['query']['pages'].values():
      for rev in img['imageinfo']:
        #Files without timestamp or url might be missing, so avoid them
        if 'timestamp' in rev and 'url' in rev:
          #Convert the timestamp to unix, then create or read an id for the current image and then
          #add the revision
          timestamp = iso_to_unix(rev['timestamp'])
          image_id = images.create_read_id(title = img['title'])
          revision_id = revisions.create(image_id = image_id,
                                         timestamp = timestamp,
                                         url = rev['url'])

          #Track successful imports
          if revision_id is not None:
            rev_count += 1
          else:
            print(f'Warning: duplicate image revision: "{img['title']}" - {rev['timestamp']}')

      img_count += 1

    print(f'{img_count} images, {rev_count} revisions')

  api_client.close()
  print('Done')

#Update the existing image index if any, or create it otherwise
def update_image_index():
  last_timestamp = revisions.read_last_timestamp()

  if last_timestamp is None:
    #The revisions table is not populated yet. Create a new index instead.
    return create_image_index()

  print ('Updating image indexes...')

  query_params = {'action': 'query', 'generator': 'recentchanges', 'grcnamespace': 6,
                  'grcstart': last_timestamp, 'grcdir': 'newer', 'grclimit': 'max',
                  'prop': 'imageinfo', 'iiprop': 'timestamp|url', 'iilocalonly': 1,
                  'iilimit': 'max',
                  'XDEBUG_SESSION': '1'}

  #Query the mediawiki server and process each parsed JSON block
  for result in api_client.query(query_params):
    for img in result['query']['pages'].values():
      if 'imageinfo' not in img:
        #The image has no revisions and has been erased
        print(f'Deleted image: {img['title']}')
        images.delete(title = img['title'])
      else:
        #The image has revisions. Create or read an id for it.
        image_id = images.create_read_id(title = img['title'])

        #Get all current timestamps associated to the image from the result. Those are potential
        #candidates for addition. The deletion candidates will be determined next.
        timestamps_to_add = [iso_to_unix(x['timestamp']) for x in img['imageinfo']]
        timestamps_to_del = []

        #Match all stored timestamps associated to the image against the current ones
        for stored_timestamp in revisions.read_timestamps(image_id = image_id):
          if stored_timestamp in timestamps_to_add:
            #The timestamp is stored already
            timestamps_to_add.remove(stored_timestamp)
          else:
            #The stored timestamp is not in the current ones anymore
            timestamps_to_del.append(stored_timestamp)

        #Remove all deletion candidates
        for timestamp in timestamps_to_del:
          revisions.delete(image_id = image_id,
                           timestamp = timestamp)
          print(f'Deleted revision: {img['title']}: {datetime.fromtimestamp(timestamp)}')

        #Create all addition candidates
        for rev in img['imageinfo']:
          timestamp = iso_to_unix(rev['timestamp'])
          if timestamp in timestamps_to_add:
            revisions.create(image_id = image_id,
                             timestamp = timestamp,
                             url = rev['url'])
            print(f'New revision: {img['title']}: {datetime.fromtimestamp(timestamp)}')

  api_client.close()
  print('Done')

try:
  update_image_index()
except KeyboardInterrupt:
  print()
except:
  raise
