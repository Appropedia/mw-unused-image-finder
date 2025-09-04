#!/usr/bin/env -S sh -c 'cd $(dirname $0); python/bin/python -m $(basename ${0%.py}) $@'

from datetime import datetime
import urllib3
import PIL
import io
import imagehash
from modules.common import config
from modules.model import db, images, revisions, hashes, unused_images, db_views
from modules.mediawiki import api_client

config.load('config.toml', warn_unknown = False)
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
                  'iilimit': 'max'}

  #Query the mediawiki server and process each parsed JSON block
  for result in api_client.query(query_params):
    if 'query' not in result or 'pages' not in result['query']: continue

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

  print('Done')

#Refresh the list of unused images
def update_unused_images():
  print('Updating unused images...')

  #Create a scratch table for downloading the images
  unused_images.create_temp_table()

  query_params = {
    'action': 'query', 'list': 'querypage', 'qppage': 'Unusedimages', 'qplimit': 'max',
  }

  img_count = 0

  #Query the mediawiki server and process each parsed JSON block
  for result in api_client.query(query_params):
    querypage_results = result['query']['querypage']['results']

    #Insert the images into the scratch table
    unused_images.insert_into_temp_table(img['title'] for img in querypage_results)

    img_count += len(querypage_results)
    print(f'{img_count} unused images')

  #The scratch table is completed. Update the unused images table with it.
  unused_images.update_from_temp_table()

  print('Done')

#Download and calculate hashes for all images that haven't been hashed yet
def update_hashes():
  print('Downloading images and calculating hashes...')

  #Create a connection pool for downloading
  pool_mgr = urllib3.PoolManager()

  revision_count = 0
  revision_total = db_views.pending_hash_total()
  for revision_id, revision_url in db_views.pending_hashes():
    revision_count += 1

    #Perform a request to download the image and get the response
    rsp = pool_mgr.request('GET', revision_url)

    #Make sure the response is 200 - OK
    if rsp.status != 200:
      print(f'{revision_count}/{revision_total} Error code {rsp.status} - {rsp.reason}: {revision_url}')
      continue

    #Read the data and store the image size
    data = rsp.data
    revisions.update_size(revision_id, len(data))

    #Open the downloaded image with PIL
    try:
      img = PIL.Image.open(io.BytesIO(data))
    except PIL.UnidentifiedImageError:
      #The image file could not be recognized. Create a null hash in its place.
      hashes.create(revision_id, (None,) * 8)
      print(f'{revision_count}/{revision_total} Not a recognized image file: {revision_url}')
      continue

    #Calculate the hash for every 90 degreee rotation of this image, then structure it as individual
    #bytes in a tuple
    new_hashes = set()  #Use a set to reduce the hashes of images with rotational symmetry
    for angle in range(0, 360, 90):
      string_hash = str(imagehash.phash(img.rotate(angle, expand = True)))
      tuple_hash = tuple(int(string_hash[i: i+2], 16) for i in range(0, len(string_hash), 2))
      new_hashes.update(set((tuple_hash,)))

    #Store the hashes
    for h in new_hashes:
      hashes.create(revision_id, h)

    print(f'{revision_count}/{revision_total} {revision_url}')

  print('Done')

try:
  update_image_index()
  update_unused_images()
  update_hashes()
except KeyboardInterrupt:
  print()
except:
  raise
