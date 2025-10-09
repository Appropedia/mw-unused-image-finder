from flask import Blueprint, abort, render_template
from modules.common import config
from modules.model import images, revisions
from modules.model.view.development import similar_images

blueprint = Blueprint('file_info', __name__)

#Route handler for the image information view
@blueprint.route('/file_info/<image_title>')
def view(image_title: str):
  image_id = images.read_id(image_title)
  if image_id is None:
    abort(404)

  #Get the revisions of the requested image
  image_revisions = [{'timestamp': timestamp, 'size': size}\
                     for (timestamp, size) in revisions.get_timestamps_and_sizes(image_id)]

  #Perform searches for similar images and append them to each revision
  for rev in image_revisions:
    rev['similar_images'] = [{'title': title, 'timestamp': timestamp} for (title, timestamp)\
                             in similar_images.search(image_title, rev['timestamp'], 8)]

  results = {
    'api_url': config.root.mediawiki_server.frontend_api(),
    'image_title': image_title,
    'revisions': image_revisions,
  }

  return render_template('development/file_info.html.jinja', **results)
