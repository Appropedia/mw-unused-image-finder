#!/usr/bin/env -S sh -c 'cd $(dirname $0); python/bin/python -m $(basename ${0%.py}) $@'

from collections.abc import Iterator
from argparse import ArgumentParser
from pathlib import Path
from urllib.parse import urlparse, unquote
from time import sleep
import urllib3
from modules.common import config
from modules.model import db
from modules.model.table import images, revisions, hashes, unused_images
from modules.model.view import pending_hashes
from modules.model.aggregate import images_without_revisions
from modules.mediawiki import api_client
from modules.utility import perceptual_hash

#Register module configurations
config.register({
  'image_updates': {
    'download_delay': 0,  #Default: No delay
    'remote_images': '',  #Default: Don't look for for local images
    'local_images': '',   #Default: Same as previous
  },
})

#Perform initialization based on configuration
@config.on_load
def _on_load():
  global g_remote_image_url
  global g_remote_image_path
  global g_local_image_path

  #Parse and validate the remote image URL, if provided
  remote_images = config.root.image_updates.remote_images
  if remote_images:
    url = urlparse(remote_images)
    if url.scheme not in ('http', 'https') or url.hostname is None or url.path == '':
      raise ValueError(f'Invalid URL for configuration image_updates.remote_images: '
                       f'{remote_images}')

    g_remote_image_url = url
    g_remote_image_path = Path(url.path.strip('/'))
  else:
    g_remote_image_url = None
    g_remote_image_path = None

  #Parse the local image path, if provided
  local_images = config.root.image_updates.local_images
  g_local_image_path = Path(local_images) if local_images else None

config.load('config.toml', warn_unknown = False)
db.go_without_flask()

#Create (or recreate) the complete image index and store it in the image and revision tables
def refresh_full_image_index(first_time: bool):
  if first_time: print('Creating initial image index...')
  else:          print('Refreshing full image index...')

  query_params = { 'action': 'query', 'generator': 'allimages', 'gailimit': 'max',
                   'prop': 'imageinfo', 'iiprop': 'timestamp|url', 'iilimit': 'max' }

  #Start a full synchronization process for the revisions
  revisions.synchronize_begin()
  img_count = 0
  rev_count = 0

  #Query the mediawiki server and process each parsed JSON block
  for result in api_client.query(query_params):
    for img in result['query']['pages'].values():
      #Create or read an id for the current image
      image_id = images.create_read_id(title = img['title'])

      for rev in img['imageinfo']:
        #Files without timestamp or url might be missing, so avoid them
        if 'timestamp' not in rev or 'url' not in rev:
          continue

        #Add each revision to the synchronization process
        is_new = revisions.synchronize_add_one(image_id = image_id,
                                               timestamp = rev['timestamp'],
                                               url = rev['url'])

        #Track successful imports
        if first_time:
          if is_new:
            rev_count += 1
          else:
            print(f'Warning: duplicate image revision: "{img['title']}" - {rev['timestamp']}')
        else:
          rev_count += 1
          if is_new:
            print(f'Added: "{img['title']}" - {rev['timestamp']}')

      img_count += 1

    print(f'{img_count} images, {rev_count} revisions')

  #Show deletions caused by the full synchronization process
  for image_id, timestamp in revisions.full_synchronize_get_deletions():
    print(f'Removed: "{images.read_title(image_id)}" - {timestamp}')

  #Finish the full synchronization process and then prune images without revisions
  revisions.full_synchronize_end()
  images_without_revisions.prune()

  print('Done')

#Update the existing image index if any, or create it otherwise
def update_image_index(full_index: bool):
  last_timestamp = revisions.read_last_timestamp()

  if last_timestamp is None:
    #The revisions table is not populated yet. Create a new index instead.
    refresh_full_image_index(first_time = True)
    return
  elif full_index == True:
    #A full index refresh has been requested
    refresh_full_image_index(first_time = False)
    return

  print ('Updating image index...')

  query_params = { 'action': 'query', 'generator': 'recentchanges', 'grcnamespace': 6,
                   'grcstart': last_timestamp, 'grcdir': 'newer', 'grclimit': 'max',
                   'prop': 'imageinfo', 'iiprop': 'timestamp|url', 'iilocalonly': 1,
                   'iilimit': 'max' }

  #Start a partial synchronization process for the revisions
  revisions.synchronize_begin()

  #Query the mediawiki server and process each parsed JSON block
  for result in api_client.query(query_params):
    if 'query' not in result or 'pages' not in result['query']: continue

    for img in result['query']['pages'].values():
      if 'imageinfo' not in img:
        #The image has no revisions and has been removed
        print(f'Removed: "{img['title']}"')
        images.delete(title = img['title'])
      else:
        #The image has revisions. Create or read an id for it.
        image_id = images.create_read_id(title = img['title'])

        for rev in img['imageinfo']:
          #Add each revision to the synchronization process
          is_new = revisions.synchronize_add_one(image_id = image_id,
                                                 timestamp = rev['timestamp'],
                                                 url = rev['url'])

          if is_new:
            print(f'Added: "{img['title']}" - {rev['timestamp']}')

  #Show deletions caused by the partial synchronization process
  for image_id, timestamp in revisions.partial_synchronize_get_deletions():
    print(f'Removed: "{images.read_title(image_id)}" - {timestamp}')

  #Finish the partial synchronization process
  revisions.partial_synchronize_end()

  print('Done')

#Refresh the list of unused images
def update_unused_images():
  print('Updating unused images...')

  #Create a scratch table for downloading the images
  unused_images.synchronize_begin()

  query_params = {
    'action': 'query', 'list': 'querypage', 'qppage': 'Unusedimages', 'qplimit': 'max',
  }

  img_count = 0

  #Query the mediawiki server and process each parsed JSON block
  for result in api_client.query(query_params):
    querypage_results = result['query']['querypage']['results']

    #Insert the images into the scratch table
    unused_images.synchronize_add_many(img['title'] for img in querypage_results)

    img_count += len(querypage_results)
    print(f'{img_count} unused images')

  #The scratch table is completed. Update the unused images table with it.
  unused_images.synchronize_end()

  print('Done')

#Download and calculate hashes for all images that haven't been hashed yet
def update_hashes():
  print('Downloading images and calculating hashes...')

  #Create a connection pool for downloading. Only one download is performed at a time, but
  #preserving open connections to potentially multiple servers might become useful for faster
  #download times.
  pool_mgr = urllib3.PoolManager()

  revision_count = 0
  revision_total = pending_hashes.total()
  for revision_id, revision_url_str in pending_hashes.get():
    revision_count += 1
    stream = None

    #Check whether files should be searched locally first by confirming that all associated globals
    #are set
    if g_remote_image_url is not None and g_remote_image_path is not None and\
       g_local_image_path is not None:
      #The file revision should be searched locally, parse its url
      revision_url = urlparse(unquote(revision_url_str))
      revision_path = Path(revision_url.path.strip('/'))

      #Compare the revision url to the (base) remote image url by comparing the scheme (item 0) and
      #netloc (item 1) fields and then by checking if the paths are relative
      if revision_url[:2] == g_remote_image_url[:2] and\
         revision_path.is_relative_to(g_remote_image_path):
        #The revision has a matching url, look for it locally
        local_path = g_local_image_path / revision_path.relative_to(g_remote_image_path)
        stream = _local_file_stream(local_path)

        if stream:
          print(f'{revision_count}/{revision_total} {local_path} => ', end = '')

    if not stream:
      #No local image available, it'll be downloaded
      print(f'{revision_count}/{revision_total} {revision_url_str} => ', end = '')

      #Perform a request to download the image and get the response
      sleep(config.root.image_updates.download_delay)
      rsp = pool_mgr.request('GET', revision_url_str, preload_content = False)

      #Make sure the response is 200 - OK
      if rsp.status != 200:
        print(f'Error code {rsp.status} - {rsp.reason}')
        continue

      #Use the stream from the response
      stream = rsp.stream()

    #Use the stream to (down)load, hash and obtain the size of the image
    status, file_size, new_hashes = perceptual_hash.calculate_phashes(stream)

    #Store the file size first
    revisions.update_size(revision_id, file_size)

    match status:
      case perceptual_hash.Status.OK:
        #Store the hashes now. Do this as the last step, as this effectively removes the image from
        #the pending hashes view.
        for h in new_hashes:
          hashes.create(revision_id, h)
        print('OK')
      case perceptual_hash.Status.OUT_OF_MEM:
        #There was not enough memory for processing the image. Don't store a hash, so this can be
        #retried later for this image.
        print('Not enough memory')
      case perceptual_hash.Status.UNSUPPORTED:
        #The image could not be processed, possibly because its type is unsupported or there was
        #another error. Store a null hash for it, so it won't be retried.
        hashes.create(revision_id, None)
        print('Not a recognized image file')

  print('Done')

#Open a local file for reading and return a stream compatible with urllib3's response streams
def _local_file_stream(pathname: Path) -> Iterator[bytes] | None:
  #Function used for generating chunks
  def generator(pathname: Path) -> Iterator[bytes]:
    with pathname.open('rb') as f:
      while True:
        chunk = f.read(65536)
        if not chunk:
          break
        yield chunk

  #Return an iterator if the file exists, otherwise return None
  return generator(pathname) if pathname.is_file() else None

#Register and parse program arguments
parser = ArgumentParser()
parser.add_argument('-fi', '--full-index',
                    action = 'store_true',
                    help = 'Forcefully update the full image index (fixes desynchronizations)')
parser.add_argument('-ji', '--just-index',
                    action = 'store_true',
                    help = 'Update the image index only (prevent downloading images for hashing)')
args = parser.parse_args()

try:
  update_image_index(full_index = args.full_index)
  update_unused_images()

  if not args.just_index:
    update_hashes()
except KeyboardInterrupt:
  print()
