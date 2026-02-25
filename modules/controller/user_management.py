from urllib.parse import quote, unquote
from flask import Blueprint, request, session, url_for, render_template, abort, g
from werkzeug.exceptions import HTTPException
from modules.controller import session_control
from modules.model.table import users, privileges
from modules.model.view import user_privileges
from modules.utility import random_password, password_rules

blueprint = Blueprint('user_management', __name__)

#Privilege names as shown in rendered pages
PRIVILEGE_LABEL = {
  'admin': 'Administrator',
  'plan': 'Planner',
  'review': 'Reviewer',
}

#Description of privileges as shown in rendered pages
PRIVILEGE_DESCRIPTION = {
  PRIVILEGE_LABEL['admin']: (
    'Can create and delete user accounts',
    'Can reset user passwords',
    'Can ban/reinstate users',
    'Can grant/revoke user privileges',
  ),
  PRIVILEGE_LABEL['plan']: (
    'Can create, modify and delete cleanup actions and reasons',
    'Can change the wikitext template and set individual/distinct/unanimous wikitext for any '
      'action or reason',
  ),
  PRIVILEGE_LABEL['review']: (
    'Can create and modify their own reviews',
  ),
}

#A brief description of user account status based on status flags
STATUS_LABEL = lambda user: 'Banned' if user['ban_status'] else \
                            'Password reset pending' if user['password_reset'] else \
                            'Active'

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

#Route handler for the main user management view
@blueprint.get('/user_management')
@session_control.login_required('admin')
def view_get() -> str:
  #Collect all user names, status flags and privileges
  user_data = tuple(
    user | { 'privileges': user_privileges.get(user['name']) }
    for user in users.read_name_status_all()
  )

  render_params = {
    'table_descriptor': {
      'fields': (
        {
          'name': 'user_name',
          'label': 'User name',
        },
        {
          'name': 'status',
          'label': 'Account status',
        },
        *({
          'name': privilege_name,
          'label': PRIVILEGE_LABEL[privilege_name],
          'type': 'checkbox',
          'allow_update': True,
        } for privilege_name in privileges.VALID_PRIVILEGES),
      ),
      'rows': tuple({
        'cells': (
          { 'value': user['name'] },
          { 'value': STATUS_LABEL(user) },
          *({
            'value': privilege_name in user['privileges']
          } for privilege_name in privileges.VALID_PRIVILEGES),
        ),
        'actions': {
          'allow_update': True,
          'update_url': url_for('user_management.user_privileges_patch',
                                user_name = _url_encode(user['name'])),
          'allow_delete': session['user_name'] != user['name'],
          'delete_url': url_for('user_management.user_delete',
                                user_name = _url_encode(user['name'])),
          'delete_warning': 'Are you sure you want to delete this user account?\n\n'
                            'This action is irreversible and all reviews made by this user will be '
                            'deleted as well. This should be done only if the user created a '
                            'considerable amount of incorrect reviews.',
          'buttons': (
            *((
              {
                'name': 'ban',
                'label': 'Ban',
                'value': '1',
                'url': url_for('user_management.user_ban_status_patch',
                               user_name = _url_encode(user['name'])),
                'method': 'PATCH',
                'warning': 'Are you sure you want to ban this user?\n\n'
                           'The user will be forcefully logged off immediately. Their reviews will '
                           'be preserved.'
              } if not user['ban_status'] else
              {
                'name': 'ban',
                'label': 'Lift ban',
                'value': '0',
                'url': url_for('user_management.user_ban_status_patch',
                               user_name = _url_encode(user['name'])),
                'method': 'PATCH',
              },
            ) if session['user_name'] != user['name'] else ()),
          )
        },
      } for user in user_data),
    },
    'privilege_description': PRIVILEGE_DESCRIPTION,
  }

  return render_template('view/user_management.jinja.html', **render_params)

#Route handler for the password update view
@blueprint.get('/user_management/password_update')
@session_control.login_required()
def password_update_get() -> str:
  render_params = {
    'user_password_update_url': url_for('user_management.user_password_udpate_patch',
                                        user_name = _url_encode(session['user_name'])),
  }

  return render_template('view/password_update.jinja.html', **render_params)

#Route handler for the user creation view
@blueprint.get('/user_management/create_user')
@session_control.login_required('admin')
def create_user_get() -> str:
  render_params = {
    'valid_privileges': {
      privilege_name: PRIVILEGE_LABEL[privilege_name]
      for privilege_name in privileges.VALID_PRIVILEGES
    },
    'privilege_description': PRIVILEGE_DESCRIPTION,
  }

  return render_template('view/create_user.jinja.html', **render_params)

#Route handler for the user password reset form
@blueprint.get('/user_management/password_reset')
@session_control.login_required('admin')
def password_reset_get() -> str:
  render_params = {
    'users': {
      user_name: url_for('user_management.user_password_reset_patch',
                         user_name = _url_encode(user_name))
      for user_name in users.read_name_all() if user_name != session['user_name']
    },
  }

  return render_template('view/password_reset.jinja.html', **render_params)

#Route handler for creating a single user
@blueprint.post('/user')
@session_control.login_required('admin')
def user_post() -> str:
  #Validate request parameters
  user_name = _validate_user_name()
  new_privileges = _validate_privileges()

  #Make sure the user name doesn't exist already
  if users.exists(user_name):
    abort(409, 'FIELD_CONFLICT,user_name')

  #Generate a new random password first
  new_password = random_password.generate_for_user()

  #This is just for the sake of data integrity, just in case the password rules are ever changed
  validity_status = password_rules.check(new_password)
  if validity_status != password_rules.Status.OK:
    abort(400, validity_status.value)

  #Create the new user account next
  user_id = users.create(user_name, new_password, True)

  #Grant the requested privileges now (if any)
  for privilege_name, is_granted in new_privileges.items():
    if is_granted:
      privileges.create(user_id, privilege_name)

  return { 'user_name': user_name, 'new_password': new_password }

#Route handler for deleting a single user
@blueprint.delete('/user/<user_name>')
@session_control.login_required('admin')
def user_delete(user_name: str) -> str:
  #Forbid self account deletion
  user_name = _url_decode(user_name)
  if user_name == session['user_name']:
    abort(403, 'FORBIDDEN,self_account_deletion')

  users.delete(user_name)

  return 'OK'

#Route handler for updating a user password
@blueprint.patch('/user/<user_name>/password_update')
@session_control.login_required()
def user_password_udpate_patch(user_name: str) -> str:
  user_name = _url_decode(user_name)

  #Validate request parameters
  _validate_password_update_parameters()

  #Forbid setting the password of another user
  if user_name != session['user_name']:
    abort(403, 'FORBIDDEN,not_own_password_update')

  #Do a password rule check
  validity_status = password_rules.check(request.form['new_password'])
  if validity_status != password_rules.Status.OK:
    abort(400, validity_status.value)

  #Validate the current password
  password_valid, _ = users.authenticate(name = session['user_name'],
                                         password = request.form['current_password'])
  if not password_valid:
    abort(400, 'INVALID_VALUE,current_password')

  #Perform the password change now
  users.update_password_and_reset_status(session['user_name'], request.form['new_password'], False)

  return 'OK'

#Route handler for reseting a user password
@blueprint.patch('/user/<user_name>/password_reset')
@session_control.login_required('admin')
def user_password_reset_patch(user_name: str) -> str:
  user_name = _url_decode(user_name)

  #Make sure the request refers to an existing user
  if not users.exists(user_name):
    abort(404, 'NOT_FOUND,user_name')

  #Forbid self password resets
  if user_name == session['user_name']:
    abort(403, 'FORBIDDEN,self_password_reset')

  #Generate a new random password
  new_password = random_password.generate_for_user()

  #This is just for the sake of data integrity, just in case the password rules are ever changed
  validity_status = password_rules.check(new_password)
  if validity_status != password_rules.Status.OK:
    abort(400, validity_status.value)

  #Update the user password now
  users.update_password_and_reset_status(user_name, new_password, True)

  return { 'user_name': user_name, 'new_password': new_password }

#Route handler for managing user privileges
@blueprint.patch('/user/<user_name>/privileges')
@session_control.login_required('admin')
def user_privileges_patch(user_name: str) -> str:
  #Retrieve the user id
  user_name = _url_decode(user_name)
  user_id = users.read_id(user_name)

  if user_id is None:
    abort(404, 'NOT_FOUND,user_name')

  #Validate and convert request form parameters
  new_privileges = _validate_privileges()

  #Forbid self removal of administrator privileges
  if 'admin' in new_privileges and not new_privileges['admin'] \
     and user_name == session['user_name'] and 'admin' in g.user_privileges:
    abort(403, 'FORBIDDEN,self_admin_demotion')

  #Update the requested privileges (if any)
  for privilege_name, is_granted in new_privileges.items():
    if is_granted:
      privileges.create(user_id, privilege_name)
    else:
      privileges.delete(user_id, privilege_name)

  return 'OK'

#Route handler for updating user status flags such as ban status
@blueprint.patch('/user/<user_name>/ban_status')
@session_control.login_required('admin')
def user_ban_status_patch(user_name: str) -> str:
  #Retrieve the user id
  user_name = _url_decode(user_name)
  user_id = users.read_id(user_name)

  if user_id is None:
    abort(404, 'NOT_FOUND,user_name')

  #Validate and convert request form parameters
  ban_status = _validate_ban_status()

  #Forbid self modification of ban satus
  if user_name == session['user_name']:
    abort(403, 'FORBIDDEN,self_ban_status_modify')

  #Update the ban status now
  users.update_ban_status(user_id, ban_status)

  return 'OK'

#Encode an arbitrary string as a URL path segment
def _url_encode(url: str) -> str:
  return quote(url, safe='', errors='replace')

#Decode an arbitrary string from a URL path segment
def _url_decode(url: str) -> str:
  return unquote(url)

#Make sure a user name is provided or abort the request
def _validate_user_name() -> str:
  if 'user_name' not in request.form:
    abort(400, 'MISSING_FIELD,user_name')

  return request.form['user_name']

#Collect privilege parameter values and ensure they're valid or abort the request
def _validate_privileges() -> dict[str, bool]:
  #Create a dictionary with all form parameters that have valid privilege names
  new_privileges = {
    key: value for key, value in request.form.items() if key in privileges.VALID_PRIVILEGES
  }

  #Make sure privilege values can be interpreted as boolean and convert accordingly
  for key, value in new_privileges.items():
    match value:
      case '0': new_privileges[key] = False
      case '1': new_privileges[key] = True
      case _:   abort(400, f'INVALID_VALUE,{key}')

  return new_privileges

#Make sure every password update parameter is present and valid or abort the request
def _validate_password_update_parameters() -> dict[str, str]:
  #Make sure all form fields are provided
  for field in ('current_password', 'new_password', 'confirmed_password'):
    if field not in request.form:
      abort(400, f'MISSING_FIELD,{field}')

  #Validate the password confirmation
  if request.form['new_password'] != request.form['confirmed_password']:
    abort(400, 'FIELD_MISMATCH,new_password,confirmed_password')

#Make sure the ban status parameter is valid or abort the request
def _validate_ban_status() -> bool:
  if 'ban' not in request.form:
    abort(400, f'MISSING_FIELD,ban')

  match request.form['ban']:
    case '0': return False
    case '1': return True
    case _:   abort(400, f'INVALID_VALUE,ban')
