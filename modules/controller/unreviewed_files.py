from flask import Blueprint, request, abort, render_template
from modules.controller import session_control
from modules.model.view import unreviewed_images

blueprint = Blueprint('unreviewed_files', __name__)

#Route handler for the unreviewed file list view
@blueprint.get('/unreviewed_files')
@session_control.login_required('review')
def get() -> str:
  #Validate and get request parameters
  limit, offset = _validate_request_range()
  category = _validate_category()

  #Get the image titles in the range and category
  results, more_results = unreviewed_images.get_range(limit, offset, category)

  render_params = {
    'limit': limit,
    'offset': offset,
    'category': request.args['category'],
    'results': results,
    'more_results': more_results,
  }

  return render_template('view/unreviewed_files.jinja.html', **render_params)

#Convert the limit and offset request arguments to integers, validate them, and provide defaults if
#absent
def _validate_request_range() -> tuple[int, int]:
  if 'limit' in request.args:
    try:
      limit = int(request.args['limit'])
    except ValueError:
      abort(400, 'Request parameter must be a number: limit')

    if limit <= 0:
      abort(400, 'Request parameter must be greater than 0: limit')
  else:
    limit = 50

  if 'offset' in request.args:
    try:
      offset = int(request.args['offset'])
    except ValueError:
      abort(400, 'Request parameter must be a number: offset')

    if offset < 0:
      abort(400, 'Request parameter must be greater than or equal to 0: offset')
  else:
    offset = 0

  return limit, offset

#Make sure the category paremeter is valid and convert it to an Enum value or abort the request
def _validate_category() -> unreviewed_images.Category:
  if 'category' not in request.args:
    return abort(400, 'Missing field: category')

  match request.args['category']:
    case 'unused_img_all_rev':     category = unreviewed_images.Category.unused_img_all_rev
    case 'used_img_old_rev':       category = unreviewed_images.Category.used_img_old_rev
    case 'used_img_all_rev':       category = unreviewed_images.Category.used_img_all_rev
    case 'used_img_all_rev_count': category = unreviewed_images.Category.used_img_all_rev_count
    case invalid_category:         return abort(400, f'Invalid category name: {invalid_category}')

  return category
