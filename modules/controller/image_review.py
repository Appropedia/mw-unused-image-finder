from flask import Blueprint, request, abort, url_for, redirect, render_template
from modules.controller import session_control
from modules.model.view import image_usage, similar_images
from modules.common import config

blueprint = Blueprint('image_review', __name__)

#Route handler for the image dealer view
@blueprint.route('/image_review')
@session_control.login_required
def deal():
  dealer = request.args.get('dealer', None)
  try:
    offset = int(request.args.get('offset', 0))
  except ValueError:
    return abort(400)

  #Choose the next image to deal based on the selected dealer
  match dealer:
    case 'unused_images':
      image_title = image_usage.largest_unused(offset)
    case _:
      return abort(400)

  if image_title is None:
    return 'The image dealer has run out of images'

  return redirect(url_for('image_review.view', image_title = image_title) +
                  f'?dealer={dealer}' +
                  f'&offset={offset}')

#Route handler for the image review view
@blueprint.route('/image_review/<image_title>')
@session_control.login_required
def view(image_title):
  dealer = request.args.get('dealer', None)
  try:
    offset = int(request.args.get('offset', 0))
  except ValueError:
    return abort(400)

  if dealer not in ['unused_images']:
    return abort(400)

  render_params = {}

  render_params['image'] = {}

  image_id,\
  render_params['image']['last_modification'],\
  render_params['image']['max_rev_size'],\
  render_params['image']['all_revs_size'],\
  render_params['image']['total_revisions']\
    = image_usage.read(image_title)

  render_params['image']['title'] = image_title

  render_params['similar_images'] = similar_images.search(image_id, 16)
  import json
  print(json.dumps(render_params['similar_images'], indent = 2))
  render_params['api_url'] = config.root.mediawiki_server.frontend_api()
  render_params['dealer'] = dealer
  render_params['next_offset'] = offset + 1

  return render_template('image_review.html.jinja', **render_params)
