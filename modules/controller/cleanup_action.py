from urllib.parse import quote, unquote
from flask import Blueprint, request, url_for, render_template, abort
from markupsafe import Markup
from werkzeug.exceptions import HTTPException
from modules.controller import session_control
from modules.model.table import cleanup_actions, cleanup_choices, wikitext as wikitext_table
from modules.model.view import cleanup_action_reason_links
from modules.model.aggregate import cleanup_action_reasons

blueprint = Blueprint('cleanup_action', __name__)

#Field size limits
NAME_MAX_LEN = 32
DESCRIPTION_MAX_LEN = 128
WIKITEXT_MAX_LEN = 256

#Route handler for the cleanup actions table
@blueprint.route('/cleanup_action', methods = ['GET', 'POST'])
@session_control.login_required
def handle_all() -> str:
  #Call the corresponding method handler
  match request.method:
    case 'GET':  return _read_all()
    case 'POST': return _create()

#Route handler for specific cleanup actions
@blueprint.route('/cleanup_action/<action>', methods = ['GET', 'PATCH', 'DELETE'])
@session_control.login_required
def handle_single(action: str) -> str:
  action = _url_decode(action)

  #Call the corresponding method handler
  match request.method:
    case 'GET':    return _read_single(action)
    case 'PATCH':  return _update(action)
    case 'DELETE': return _delete(action)

#Route handler for reasons linked to actions
@blueprint.route('/cleanup_action/<action>/reason_link/<reason>', methods = ['PATCH'])
@session_control.login_required
def handle_reason(action: str, reason: str) -> str:
  action = _url_decode(action)
  reason = _url_decode(reason)
  return _update_reason(action, reason)

#Route handler for wikitext liked to actions
@blueprint.route('/cleanup_action/<action>/wikitext/<category>', methods = ['PATCH'])
@session_control.login_required
def handle_wikitext(action: str, category: str) -> str:
  action = _url_decode(action)
  return _update_wikitext(action, category)

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

#Create a new cleanup action
def _create() -> str:
  _validate_name_description()
  status = cleanup_actions.create(request.form['name'], request.form['description'])
  return _handle_cleanup_actions_return_status(status)

#Read all cleanup actions and present them in a table
def _read_all() -> str:
  name_description_list = cleanup_actions.read_name_description_all()

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
            'link_url': url_for('cleanup_action.handle_single', action = _url_encode(name)) },
          { 'value': description },
        ),
        'actions': {
          'allow_update': True,
          'allow_delete': True,
          'form_url': url_for('cleanup_action.handle_single', action = _url_encode(name)),
          'buttons': (
            *(({
              'name': 'move_position',
              'label': Markup('&uarr;'),
              'value': 'backward',
              'method': 'PATCH',
            },) if index > 0 else ()),
            *(({
              'name': 'move_position',
              'label': Markup('&darr;'),
              'value': 'forward',
              'method': 'PATCH',
            },) if index < len(name_description_list) - 1 else ()),
          ),
        },
      } for index, (name, description) in enumerate(name_description_list)),
    },
  }

  return render_template('view/cleanup_action_all.jinja.html', **render_params)

#Read a single cleanup action and present its details
def _read_single(action: str) -> str:
  action_description = cleanup_actions.read_description(action)

  if action_description is None: abort(404)

  cleanup_reasons = cleanup_action_reason_links.get_reasons_linked_to_action(action)

  #Reordering is limited to the cleanup reasons that are linked, which always come first in the
  #query. The amount of linked reasons is inferred by finding the offset of the first row that is
  #unlinked. In case all all rows are linked the limit is set to their total.
  link_count = next((index for index, row in enumerate(cleanup_reasons) if not row[0]),
                    len(cleanup_reasons))

  wikitext_contents = wikitext_table.read_cleanup_action(cleanup_actions.read_id(action))

  render_params = {
    'action_name': action,
    'description': action_description,
    'table_descriptor': {
      'fields': (
        {
          'name': 'valid_choice',
          'label': 'Valid choice',
          'type': 'checkbox',
        },
        {
          'name': 'name',
          'label': 'Name',
        },
        {
          'name': 'description',
          'label': 'Description',
        },
      ),
      'rows': tuple({
        'cells': (
          { 'value': is_linked },
          { 'value': reason,
            'link_url': url_for('cleanup_reason.handle_single', reason = _url_encode(reason)) },
          { 'value': reason_description },
        ),
        'actions': {
          'form_url': url_for('cleanup_action.handle_reason', action = _url_encode(action),
                                                              reason = _url_encode(reason)),
          'buttons': (
            *(({
              'name': 'valid_choice',
              'label': 'Disallow',
              'value': '0',
              'method': 'PATCH',
            },) if is_linked else ({
              'name': 'valid_choice',
              'label': 'Allow',
              'value': '1',
              'method': 'PATCH',
            },)),
            *(({
              'name': 'move_position',
              'label': Markup('&uarr;'),
              'value': 'backward',
              'method': 'PATCH',
            },) if index > 0 and index < link_count else ()),
            *(({
              'name': 'move_position',
              'label': Markup('&darr;'),
              'value': 'forward',
              'method': 'PATCH',
            },) if index < len(cleanup_reasons) - 1 and index < link_count - 1 else ()),
          ),
        },
      } for index, (is_linked, reason, reason_description) in enumerate(cleanup_reasons)),
    },
    'WIKITEXT_MAX_LEN': WIKITEXT_MAX_LEN,
    'individual_wikitext': wikitext_contents['individual'],
    'distinct_wikitext': wikitext_contents['distinct'],
    'unanimous_wikitext': wikitext_contents['unanimous'],
  }

  return render_template('view/cleanup_action_single.jinja.html', **render_params)

#Update either the position or the name and description of a cleanup action
def _update(action: str) -> str:
  if 'move_position' in request.form:
    #Reordering parameter present, act according to its value
    match request.form['move_position']:
      case 'backward':
        status = cleanup_actions.swap(action, cleanup_actions.Direction.BACKWARD)
        return _handle_cleanup_actions_return_status(status)
      case 'forward':
        status = cleanup_actions.swap(action, cleanup_actions.Direction.FORWARD)
        return _handle_cleanup_actions_return_status(status)
      case _:
        abort(400, 'INVALID_MOVE_DIRECTION')

  #No reordering parameter present, treat this as an update request instead
  _validate_name_description()
  status = cleanup_actions.update(action, request.form['name'], request.form['description'])
  return _handle_cleanup_actions_return_status(status)

#Delete a single cleanup action
def _delete(action: str) -> str:
  status = cleanup_actions.delete(action)
  return _handle_cleanup_actions_return_status(status)

#Update either the position or the valid choice status of a reason linked to an action
def _update_reason(action: str, reason: str) -> str:
  if 'move_position' in request.form:
    #Reordering parameter present, act according to its value
    match request.form['move_position']:
      case 'backward':
        status = cleanup_action_reasons.swap(action, reason, cleanup_choices.Direction.BACKWARD)
        return _handle_cleanup_action_reasons_return_status(status)
      case 'forward':
        status = cleanup_action_reasons.swap(action, reason, cleanup_choices.Direction.FORWARD)
        return _handle_cleanup_action_reasons_return_status(status)
      case _:
        abort(400, 'INVALID_MOVE_DIRECTION')

  #No reordering parameter present, treat this as an update request instead
  valid_choice = _validate_valid_choice()
  status = cleanup_action_reasons.update(action, reason, valid_choice);
  return _handle_cleanup_action_reasons_return_status(status)

#Update the wikitext of a cleanup action
def _update_wikitext(action: str, category: str) -> str:
  #Validate request parameters
  _validate_wikitext()

  #Retrieve the cleanup action id and validate
  cleanup_action_id = cleanup_actions.read_id(action)

  if cleanup_action_id is None:
    abort(404, 'NOT_FOUND,cleanup_action')

  #Store the wikitext after all checks are completed
  wikitext = request.form['wikitext']
  status = wikitext_table.write_cleanup_action(cleanup_action_id, category,
                                               wikitext if wikitext != '' else None)
  return _handle_wikitext_table_return_status(status)

#Encode an arbitrary string as a URL path segment
def _url_encode(url: str) -> str:
  return quote(url, safe='', errors='replace')

#Decode an arbitrary string from a URL path segment
def _url_decode(url: str) -> str:
  return unquote(url)

#Make sure the valid_choice query parameter is valid or abort the request
def _validate_valid_choice() -> bool:
  if 'valid_choice' not in request.form:
    abort(400, 'MISSING_FIELD,valid_choice')

  #Make sure valid_choice can be interpreted as boolean and convert accordingly
  match request.form['valid_choice']:
    case '0': return False
    case '1': return True
    case _:   abort(400, 'INVALID_VALUE,valid_choice')

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

#Handle the return status of a cleanup_actions module call, returning either 200 - 'OK' or the
#status enumeration name accompanied by the corresponding HTTP error code
def _handle_cleanup_actions_return_status(status: cleanup_actions.Status) -> str:
  match status:
    case cleanup_actions.Status.SUCCESS:
      return 'OK'
    case cleanup_actions.Status.NAME_CONFLICT:
      abort(409, 'FIELD_CONFLICT,name')
    case cleanup_actions.Status.POSITION_CONFLICT:
      abort(409, 'FIELD_CONFLICT,position')
    case cleanup_actions.Status.NON_EXISTENT_ACTION:
      abort(404, 'NOT_FOUND,cleanup_action')
    case _:
      abort(500, status.name)

#Handle the return status of a cleanup_action_reasons module call, returning either 200 - 'OK' or a
#simplified error message accompanied by the corresponding HTTP error code
def _handle_cleanup_action_reasons_return_status(status: cleanup_action_reasons.Status) -> str:
  match status:
    case cleanup_action_reasons.Status.SUCCESS:
      return 'OK'
    case cleanup_action_reasons.Status.POSITION_CONFLICT:
      abort(409, 'FIELD_CONFLICT,position')
    case cleanup_action_reasons.Status.NON_EXISTENT_LINK:
      abort(404, 'NOT_FOUND,cleanup_action_reason_link')
    case cleanup_action_reasons.Status.NON_EXISTENT_ACTION:
      abort(404, 'NOT_FOUND,cleanup_action')
    case cleanup_action_reasons.Status.NON_EXISTENT_REASON:
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
