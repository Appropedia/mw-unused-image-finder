from flask import Blueprint, request, abort, g, redirect, url_for, render_template
from werkzeug.exceptions import HTTPException
from modules.controller import session_control
from modules.model.table import image_concessions
from modules.model.view import image_revisions, similar_images
from modules.model.view import cleanup_action_reason_links, review_details
from modules.model.relation import image_candidates, review_store
from modules.common import config

blueprint = Blueprint('image_review', __name__)

#Field size limits
COMMENTS_MAX_LEN = 256

#Register module configurations
config.register({
  'image_dealer': {
    'concession_period': 300,   #Images are reserved for every review author for 5 minutes
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
    case 'unused_img_all_rev':     cat = image_candidates.Category.unused_img_all_rev
    case 'used_img_old_rev':       cat = image_candidates.Category.used_img_old_rev
    case 'used_img_all_rev':       cat = image_candidates.Category.used_img_all_rev
    case 'used_img_all_rev_count': cat = image_candidates.Category.used_img_all_rev_count
    case _:                        return abort(400, 'INVALID_VALUE,category')

  #Choose the next image to deal based on the selected category
  image_title = image_candidates.acquire_next(g.user_id,
                                              config.root.image_dealer.concession_period,
                                              cat,
                                              prev_image)

  if image_title is None:
    return 'The image dealer has run out of images'

  return redirect(url_for('image_review.handle_review',
                          image_title = image_title, category = category))

#Route handler for the image review view
@blueprint.route('/image_review/<image_title>', methods = ['GET', 'PUT'])
@session_control.login_required
def handle_review(image_title: str):
  #Call the corresponding method handler
  match request.method:
    case 'GET': return _read(image_title)
    case 'PUT': return _update(image_title)

#Error handler for this blueprint
@blueprint.errorhandler(HTTPException)
def request_failed(e: HTTPException) -> tuple[str, int] | HTTPException:
  if request.method == 'GET':
    #Give back the unmodified exception to the default handler in case of GET requests, since any
    #related error response is intended to be handled by browsers
    return e
  else:
    #Error responses for any other request methods are rendered as unformatted text, as they're
    #intended to be handled by frontend scripts
    return e.description, e.code

#Present a view for viewing, editting or creating image reviews
def _read(image_title) -> str:
  #Read and validate request arguments
  category = request.args.get('category', None)

  if category != None and category not in ('unused_img_all_rev', 'used_img_old_rev',
                                           'used_img_all_rev', 'used_img_all_rev_count'):
    return abort(400, f'Invalid category name: {category}')

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

  if image_id is None: abort(404)

  #Add all available cleanup actions and reasons to the render parameters
  render_params['cleanup_actions'] = cleanup_action_reason_links.get_actions_and_reasons()

  #If a review for the image exists already, add its information to the render parameters as well
  render_params['review_data'] = review_details.get_single(image_id)

  #Get all similar images and add the results to the render parameters
  render_params['similar_images'] = similar_images.search(image_id, 12)

  #Write the concession so other users get other images during the concession period
  image_concessions.write(g.user_id, image_id)

  #Note: The image_candidates.acquire_next function call in the image dealer endpoint does also
  #write the concession before redirecting to this endpoint, so this operation may seem redundant.
  #The concession is also made here in case of users sharing URLs to the served images, making it
  #less probable to offer that same image to yet another user.

  return render_template('view/image_review.jinja.html', **render_params)

#Process a review write request
def _update(image_title) -> str:
  _validate_update_args
  status = review_store.write(image_title, g.user_id, request.json)
  return _handle_reviews_return_status(status)

#Make sure the update query parameters are valid or abort the request
def _validate_update_args() -> None:
  #Validate general fields
  if not request.is_json:
    abort(400, 'INVALID_FORM_FORMAT')

  if 'comments' not in request.json:
    abort(400, 'MISSING_FIELD,comments')

  if not isinstance(request.json['comments'], str):
    abort(400, 'INVALID_TYPE,comments')

  if len(request.json['comments']) > COMMENTS_MAX_LEN:
    abort(400, 'FIELD_TOO_LONG,comments')

  if 'revisions' not in request.json:
    abort(400, 'MISSING_FIELD,revisions')

  if not isinstance(request.json['revisions'], dict):
    abort(400, 'INVALID_TYPE,revisions')

  #Validate action/reason fields for every revision
  for key, value in request.json['revisions'].items():
    if 'action' not in value:
      abort(400, 'MISSING_FIELD,action')

    if not isinstance(value['action'], str):
      abort(400, 'INVALID_TYPE,action')

    if 'reason' not in value:
      abort(400, 'MISSING_FIELD,reason')

    if not isinstance(value['reason'], str):
      abort(400, 'INVALID_TYPE,action')

#Handle the return status of a reviews module call, returning either 200 - 'OK' or a simplified
#error message accompanied by the corresponding HTTP error code
def _handle_reviews_return_status(status: review_store.Status) -> str:
  match status:
    case review_store.Status.SUCCESS:
      return 'OK'
    case review_store.Status.NON_EXISTENT_IMAGE:
      abort(404, 'NOT_FOUND,image')
    case review_store.Status.NON_EXISTEN_REVISION:
      abort(404, 'NOT_FOUND,revision')
    case review_store.Status.NON_EXISTENT_ACTION:
      abort(404, 'NOT_FOUND,cleanup_action')
    case review_store.Status.NON_EXISTENT_REASON:
      abort(404, 'NOT_FOUND,cleanup_reason')
    case _:
      abort(500, status.name)
