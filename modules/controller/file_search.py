from flask import Blueprint, request, render_template, abort
from modules.controller import session_control
from modules.model.table import images

blueprint = Blueprint('file_search', __name__)

#Route handler for the image dealer view
@blueprint.get('/file_search')
@session_control.login_required()
def view_get() -> str:
  #Validate and get the limit and offset request parameters
  limit, offset = _validate_request_range()

  render_params = {
    'limit': limit,
    'offset': offset,
  }

  if 'term' in request.args:
    #If a search term is provided perform the image title search
    results, more_results = images.get_range(limit, offset, request.args['term'])

    render_params |= {
      'more_results': more_results,
      'term': request.args['term'],
      'results': results,
    }

  return render_template('view/file_search.jinja.html', **render_params)

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
