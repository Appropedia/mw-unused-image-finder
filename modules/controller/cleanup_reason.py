from urllib.parse import quote, unquote
from flask import Blueprint, request, url_for, render_template, abort
from werkzeug.exceptions import HTTPException
from modules.controller import session_control
from modules.model.table import cleanup_reasons
from modules.model.view import cleanup_action_reason_links

blueprint = Blueprint('cleanup_reason', __name__)

#Field size limits
NAME_MAX_LEN = 32
DESCRIPTION_MAX_LEN = 128

#Route handler for the cleanup reasons table
@blueprint.route('/cleanup_reason', methods = ['GET', 'POST'])
@session_control.login_required
def handle_all() -> str:
  #Call the corresponding method handler
  match request.method:
    case 'GET':  return _read_all()
    case 'POST': return _create()

#Route handler for specific cleanup reasons
@blueprint.route('/cleanup_reason/<reason>', methods = ['GET', 'PATCH', 'DELETE'])
@session_control.login_required
def handle_single(reason: str) -> str:
  reason = _url_decode(reason)

  #Call the corresponding method handler
  match request.method:
    case 'GET':    return _read_single(reason)
    case 'PATCH':  return _update(reason)
    case 'DELETE': return _delete(reason)

#Error handler for this blueprint
@blueprint.errorhandler(HTTPException)
def bad_request(e: HTTPException) -> tuple[str, int] | HTTPException:
  if request.method == 'GET':
    #Give back the unmodified exception to the default handler in case of GET requests, since any
    #related error response is intended to be handled by browsers
    return e
  else:
    #Error responses for any other request methods are rendered as unformatted text, as they're
    #intended to be handled by frontend scripts
    return e.description, e.code

#Create a new cleanup reason
def _create() -> str:
  _validate_name_description()
  status = cleanup_reasons.create(request.form['name'], request.form['description'])
  return _handle_cleanup_reasons_return_status(status)

#Read all cleanup reasons and present them in a table
def _read_all() -> str:
  render_params = {
    'fields': (
      {
        'name': 'name',
        'label': 'Name',
        'allow_update': True,
        'allow_create': True,
        'type': 'input',
        'max_len': NAME_MAX_LEN,
      },
      {
        'name': 'description',
        'label': 'Description',
        'allow_update': True,
        'allow_create': True,
        'type': 'input',
        'max_len': DESCRIPTION_MAX_LEN,
        'size': DESCRIPTION_MAX_LEN // 2,
      },
    ),
    'data': tuple({
      'link_url': url_for('cleanup_reason.handle_single', reason = _url_encode(row[0])),
      'form_url': url_for('cleanup_reason.handle_single', reason = _url_encode(row[0])),
      'content': row,
    } for row in cleanup_reasons.read_all()),
    'link_field': 'name',
    'allow_create': True,
    'allow_update': True,
    'allow_delete': True,
  }

  return render_template('view/cleanup_reason_all.jinja.html', **render_params)

#Read a single cleanup reason and present its details
def _read_single(reason: str) -> str:
  description = cleanup_reasons.read_description(reason)

  if description is None: abort(404)

  render_params = {
    'reason_name': reason,
    'description': description,
    'cleanup_actions': tuple({
      'name': action_name,
      'url': url_for('cleanup_action.handle_single', action = action_name),
    } for action_name in cleanup_action_reason_links.get_actions_linked_to_reason(reason)),
  }

  return render_template('view/cleanup_reason_single.jinja.html', **render_params)

#Update the name and description of a cleanup reason
def _update(reason: str) -> str:
  _validate_name_description()
  status = cleanup_reasons.update(reason, request.form['name'], request.form['description'])
  return _handle_cleanup_reasons_return_status(status)

#Delete a single cleanup reason
def _delete(reason: str) -> str:
  status = cleanup_reasons.delete(reason)
  return _handle_cleanup_reasons_return_status(status)

#Encode an arbitrary string as a URL path segment
def _url_encode(url: str) -> str:
  return quote(url, safe='', errors='replace')

#Decode an arbitrary string from a URL path segment
def _url_decode(url: str) -> str:
  return unquote(url)

#Make sure the name and description query parameters are valid or abort the request
def _validate_name_description() -> None:
  if 'name' not in request.form or len(request.form['name']) == 0:
    abort(400, 'MISSING_FIELD,name')

  if len(request.form['name']) > NAME_MAX_LEN:
    abort(400, 'FIELD_TOO_LONG,name')

  if 'description' not in request.form or len(request.form['description']) == 0:
    abort(400, 'MISSING_FIELD,description')

  if len(request.form['description']) > DESCRIPTION_MAX_LEN:
    abort(400, 'FIELD_TOO_LONG,description')

#Handle the return status of a cleanup_reasons module call, returning either 200 - 'OK' or the
#status enumeration name accompanied by the corresponding HTTP error code
def _handle_cleanup_reasons_return_status(status: cleanup_reasons.Status) -> str:
  match status:
    case cleanup_reasons.Status.SUCCESS:
      return 'OK'
    case cleanup_reasons.Status.NAME_CONFLICT:
      abort(409, 'FIELD_CONFLICT,name')
    case cleanup_reasons.Status.NON_EXISTENT_REASON:
      abort(404, 'NOT_FOUND,cleanup_reason')
    case _:
      abort(500, status.name)
