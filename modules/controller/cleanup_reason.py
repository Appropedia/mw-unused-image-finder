from urllib.parse import quote, unquote
from flask import Blueprint, request, url_for, render_template, abort
from werkzeug.exceptions import HTTPException
from modules.controller import session_control
from modules.model.table import cleanup_reasons, wikitext as wikitext_table
from modules.model.view import cleanup_action_reason_links

blueprint = Blueprint('cleanup_reason', __name__)

#Field size limits
NAME_MAX_LEN = 32
DESCRIPTION_MAX_LEN = 128
WIKITEXT_MAX_LEN = 256

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

#Route handler for creating a new cleanup reason
@blueprint.post('/cleanup_reason')
@session_control.login_required('plan')
def post() -> str:
  _validate_name_description()
  status = cleanup_reasons.create(request.form['name'], request.form['description'])
  return _handle_cleanup_reasons_return_status(status)

#Route handler for the main cleanup reasons view
@blueprint.get('/cleanup_reason')
@session_control.login_required('plan')
def view_all_get() -> str:
  render_params = {
    'table_descriptor': {
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
      'rows': tuple({
        'cells': (
          { 'value': name,
            'link_url': url_for('cleanup_reason.view_single_get', reason = _url_encode(name)) },
          { 'value': description },
        ),
        'actions': {
          'allow_update': True,
          'update_url': url_for('cleanup_reason.patch', reason = _url_encode(name)),
          'allow_delete': True,
          'delete_url': url_for('cleanup_reason.delete', reason = _url_encode(name)),
        },
      } for name, description in cleanup_reasons.read_name_description_all()),
      'create_url': url_for('cleanup_reason.post'),
    },
  }

  return render_template('view/cleanup_reason_all.jinja.html', **render_params)

#Route handler for the single cleanup reason view
@blueprint.get('/cleanup_reason/<reason>')
@session_control.login_required('plan')
def view_single_get(reason: str) -> str:
  reason = _url_decode(reason)
  description = cleanup_reasons.read_description(reason)

  if description is None: abort(404)

  wikitext_contents = wikitext_table.read_cleanup_reason(cleanup_reasons.read_id(reason))

  render_params = {
    'reason_name': reason,
    'description': description,
    'cleanup_actions': tuple({
      'name': action_name,
      'url': url_for('cleanup_action.view_single_get', action = _url_encode(action_name)),
    } for action_name in cleanup_action_reason_links.get_actions_linked_to_reason(reason)),
    'WIKITEXT_MAX_LEN': WIKITEXT_MAX_LEN,
    'distinct_wikitext_content': wikitext_contents,
    'distinct_wikitext_url': url_for('cleanup_reason.wikitext_update',
                                     reason = _url_encode(reason)),
  }

  return render_template('view/cleanup_reason_single.jinja.html', **render_params)

#Route handler for updating the name and description of a cleanup reason
@blueprint.patch('/cleanup_reason/<reason>')
@session_control.login_required('plan')
def patch(reason: str) -> str:
  reason = _url_decode(reason)
  _validate_name_description()
  status = cleanup_reasons.update(reason, request.form['name'], request.form['description'])
  return _handle_cleanup_reasons_return_status(status)

#Route handler for deleting a single cleanup reason
@blueprint.delete('/cleanup_reason/<reason>')
@session_control.login_required('plan')
def delete(reason: str) -> str:
  reason = _url_decode(reason)
  status = cleanup_reasons.delete(reason)
  return _handle_cleanup_reasons_return_status(status)

#Route handler for updating the wikitext of a cleanup reason
@blueprint.patch('/cleanup_reason/<reason>/wikitext')
@session_control.login_required('plan')
def wikitext_update(reason: str) -> str:
  reason = _url_decode(reason)

  #Validate request parameters
  _validate_wikitext()

  #Retrieve the cleanup reason id and validate
  cleanup_reason_id = cleanup_reasons.read_id(reason)

  if cleanup_reason_id is None:
    abort(404, 'NOT_FOUND,cleanup_reason')

  #Store the wikitext after all checks are completed
  wikitext = request.form['wikitext']
  status = wikitext_table.write_cleanup_reason(cleanup_reason_id,
                                               wikitext if wikitext != '' else None)
  return _handle_wikitext_table_return_status(status)

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

#Make sure the wikitext query parameters are valid or abort the request
def _validate_wikitext() -> None:
  if 'wikitext' not in request.form:
    abort(400, 'MISSING_FIELD,wikitext')
  if len(request.form['wikitext']) > WIKITEXT_MAX_LEN:
    abort(400, 'FIELD_TOO_LONG,wikitext')

#Handle the return status of a cleanup_reasons module call, returning either 200 - 'OK' or a
#simplified error message accompanied by the corresponding HTTP error code
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

#Handle the return status of a wikitext table module call, returning either 200 - 'OK' or a
#simplified error message accompanied by the corresponding HTTP error code
def _handle_wikitext_table_return_status(status: wikitext_table.Status) -> str:
  match status:
    case wikitext_table.Status.SUCCESS:
      return 'OK'
    case wikitext_table.Status.INVALID_CATEGORY:
      abort(404, 'NOT_FOUND,category')
