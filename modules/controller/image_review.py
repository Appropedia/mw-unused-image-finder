from flask import Blueprint, request, abort, g, redirect, url_for, render_template
from modules.controller import session_control
from modules.model import image_concessions
from modules.model.view import image_usage, image_revisions, similar_images
from modules.model.relation import image_candidates
from modules.common import config

blueprint = Blueprint('image_review', __name__)

#Register module configurations
config.register({
  'image_dealer': {
    'concession_period': 300,   #Images are reserved for every reviewer for 5 minutes
  },
})

#Route handler for the image dealer view
@blueprint.route('/image_review')
@session_control.login_required
def deal():
  #Read and validate request arguments
  prev_image = request.args.get('prev_image', None)
  category = request.args.get('category', None)
  match category:
    case 'unused_img_all_rev':     cat = image_usage.Category.unused_img_all_rev
    case 'used_img_old_rev':       cat = image_usage.Category.used_img_old_rev
    case 'used_img_all_rev':       cat = image_usage.Category.used_img_all_rev
    case 'used_img_all_rev_count': cat = image_usage.Category.used_img_all_rev_count
    case _:                        return abort(400)

  #Choose the next image to deal based on the selected category
  image_title = image_candidates.acquire_next(g.user_id,
                                              config.root.image_dealer.concession_period,
                                              cat,
                                              prev_image)

  if image_title is None:
    return 'The image dealer has run out of images'

  return redirect(url_for('image_review.view', image_title = image_title, category = category))

#Route handler for the image review view
@blueprint.route('/image_review/<image_title>', methods = ['GET', 'PUT'])
@session_control.login_required
def view(image_title: str):
  if request.method == 'PUT':
    #Reviews are only simulated to be saved for now
    return 'Review saved!'

  #Read and validate request arguments
  category = request.args.get('category', None)

  if category != None and category not in ('unused_img_all_rev', 'used_img_old_rev',
                                           'used_img_all_rev', 'used_img_all_rev_count'):
    return abort(400)

  #Start populating the template render parameters
  render_params = {}
  render_params['api_url'] = config.root.mediawiki_server.frontend_api()
  render_params['category'] = category
  render_params['image'] = {}
  render_params['image']['title'] = image_title

  #Get the image summary and add it to the render parameters
  image_id,\
  render_params['image']['last_modification'],\
  render_params['image']['max_rev_size'],\
  render_params['image']['all_revs_size'],\
  render_params['image']['total_revisions']\
    = image_revisions.get_image_summary(image_title)

  #Get all similar images and add the results to the render parameters
  render_params['similar_images'] = similar_images.search(image_id, 12)

  #Write the concession so other users get other images during the concession period
  image_concessions.write(g.user_id, image_id)

  #Note: The image_candidates.acquire_next function call in the image dealer endpoint does also
  #write the concession before redirecting to this endpoint, so this operation may seem redundant.
  #The concession is also made here in case of users sharing URLs to the served images, making it
  #less probable to offer that same image to yet another user.

  return render_template('image_review.html.jinja', **render_params)
