from urllib.parse import quote, unquote
from flask import Blueprint, request, session, url_for, render_template, abort, flash
from werkzeug.exceptions import HTTPException
from modules.controller import session_control
from modules.model.table import users, privileges
from modules.model.view import user_privileges
from modules.utility import random_password, password_rules

blueprint = Blueprint('user_management', __name__)

#This string is prefixed to every request form parameter name referring to a privilege (namespace
#separation)
PRIVILEGE_PREFIX = 'privilege-'

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

#Route handler for the main user management view
@blueprint.route('/user_management')
@session_control.login_required('admin')
def handle_all() -> str:
  return _read_all()

#Route handler for specific user account modification actions
@blueprint.route('/user_management/user/<user_name>', methods = ['PATCH', 'DELETE'])
@session_control.login_required('admin')
def handle_single(user_name: str) -> str:
  user_name = _url_decode(user_name)

  #Call the corresponding method handler
  match request.method:
    case 'PATCH': return _update(user_name)
    case 'DELETE': return _delete(user_name)

#Route handler for the user creation form
@blueprint.route('/user_management/create_user', methods = ['GET', 'POST'])
@session_control.login_required('admin')
def create_user():
  match request.method:
    case 'GET': return _create_user_form()
    case 'POST': return _create_user()

#Route handler for the user password reset form
@blueprint.route('/user_management/password_reset', methods = ['GET', 'POST'])
@session_control.login_required('admin')
def password_reset():
  match request.method:
    case 'GET': return _password_reset_form()
    case 'POST': return _password_reset()

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

#Read information regarding all users and present it in a table
def _read_all() -> str:
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
          'name': PRIVILEGE_PREFIX + privilege_name,
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
          'allow_delete': session['user_name'] != user['name'],
          'delete_warning': 'Are you sure you want to delete this user account?\n\n'
                            'This action is irreversible and all reviews made by this user will be '
                            'deleted as well. This should be done only if the user created a '
                            'considerable amount of incorrect reviews.',
          'form_url': url_for('user_management.handle_single',
                              user_name = _url_encode(user['name'])),
          'buttons': (
            *((
              {
                'name': 'ban',
                'label': 'Ban',
                'value': '1',
                'method': 'PATCH',
                'warning': 'Are you sure you want to ban this user?\n\n'
                           'The user will be forcefully logged off immediately. Their reviews will '
                           'be preserved.'
              } if not user['ban_status'] else
              {
                'name': 'ban',
                'label': 'Lift ban',
                'value': '0',
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

#Update the privileges or ban/unban a user
def _update(user_name: str) -> str:
  #Retrieve the user id
  user_id = users.read_id(user_name)

  if user_id is None:
    abort(404, 'NOT_FOUND,user_name')

  #Validate and convert request form parameters if present
  ban_status = _validate_ban_status()
  new_privileges = _validate_privileges()

  #Update the ban status if requested
  if ban_status is not None:
    users.update_ban_status(user_id, ban_status)

  #Forbid self removal of administrator privileges
  if 'admin' in new_privileges and not new_privileges['admin'] \
     and user_name == session['user_name'] and user_privileges.check(session['user_name'], 'admin'):
    abort(403, 'FORBIDDEN,self_admin_demotion')

  #Update the requested privileges (if any)
  for privilege_name, is_granted in new_privileges.items():
    if is_granted:
      privileges.create(user_id, privilege_name)
    else:
      privileges.delete(user_id, privilege_name)

  return 'OK'

#Delete a single user
def _delete(user_name: str) -> str:
  #Forbid self account deletion
  if user_name == session['user_name']:
    abort(403, 'FORBIDDEN,self_account_deletion')

  users.delete(user_name)

  return 'OK'

#Render the user creation form template
def _create_user_form() -> str:
  render_params = {
    'valid_privileges': {
      PRIVILEGE_PREFIX + privilege_name: PRIVILEGE_LABEL[privilege_name]
      for privilege_name in privileges.VALID_PRIVILEGES
    },
    'privilege_description': PRIVILEGE_DESCRIPTION,
  }

  return render_template('view/create_user.jinja.html', **render_params)

#Process post requests for the user creation form template
def _create_user() -> str:
  #Validate request parameters
  user_name = _validate_user_name()
  new_privileges = _validate_privileges()

  #Make sure the user name doesn't exist already
  if users.exists(user_name):
    flash('A user under that name exists already', 'error')
    return _create_user_form()

  #Generate a new random password first
  new_password = random_password.generate_for_user()

  #This is just for the sake of data integrity, just in case the password rules are ever changed
  validity_status = password_rules.check(new_password)
  if validity_status != password_rules.Status.OK:
    flash(validity_status.value, 'error')
    return _create_user_form()

  #Create the new user account next
  user_id = users.create(user_name, new_password, True)

  #Grant the requested privileges now (if any)
  for privilege_name, is_granted in new_privileges.items():
    if is_granted:
      privileges.create(user_id, privilege_name)

  flash(f'New account created for user {user_name} with temporary password: {new_password}')

  #Render the same template but now with the flashed message
  return _create_user_form()

#Render the password reset form template
def _password_reset_form() -> str:
  render_params = {
    'user_names': tuple(name for name in users.read_name_all() if name != session['user_name'])
  }

  return render_template('view/password_reset.jinja.html', **render_params)

#Process post requests for the password reset form template
def _password_reset() -> str:
  #Validate request parameters
  user_name = _validate_existing_user_name()

  #Forbid self password resets
  if user_name == session['user_name']:
    abort(403, 'FORBIDDEN,self_password_reset')

  #Generate the new random password now
  new_password = random_password.generate_for_user()

  #This is just for the sake of data integrity, just in case the password rules are ever changed
  validity_status = password_rules.check(new_password)
  if validity_status != password_rules.Status.OK:
    flash(validity_status.value, 'error')
    return _password_reset_form()

  #Update the user password to the random one, then flash it once
  users.update_password_and_reset_status(user_name, new_password, True)

  flash(f'New password generated for {user_name}: {new_password}')

  #Render the same template but now with the flashed message
  return _password_reset_form()

#Encode an arbitrary string as a URL path segment
def _url_encode(url: str) -> str:
  return quote(url, safe='', errors='replace')

#Decode an arbitrary string from a URL path segment
def _url_decode(url: str) -> str:
  return unquote(url)

#Check for a ban status parameter in the request form, make sure it's valid and return it, or abort
#the request if invalid
def _validate_ban_status() -> bool | None:
  #Validate and convert the ban parameter if present
  if 'ban' in request.form:
    match request.form['ban']:
      case '0':
        return False
      case '1':
        return True
      case _:
        abort(400, 'INVALID_VALUE,ban')
  else:
    return None

#Check for any valid privilege parameter in the request form, make sure they're valid and return
#them, or abort the request if any of them is invalid
def _validate_privileges() -> dict[str, bool]:
  #Create a dictionary with all form parameters that start with the privilege prefix, removing said
  #prefix in the process
  new_privileges = {
    key.removeprefix(PRIVILEGE_PREFIX): value
    for key, value in request.form.items() if key.startswith(PRIVILEGE_PREFIX) and
      key.removeprefix(PRIVILEGE_PREFIX) in privileges.VALID_PRIVILEGES
  }

  #Make sure privilege values can be interpreted as boolean and convert accordingly
  for key, value in new_privileges.items():
    match value:
      case '0': new_privileges[key] = False
      case '1': new_privileges[key] = True
      case _:   abort(400, f'INVALID_VALUE,{key}')

  return new_privileges

#Make sure a user name is provided or abort the request
def _validate_user_name() -> str:
  if 'user_name' not in request.form:
    abort(400, 'MISSING_FIELD,user_name')

  return request.form['user_name']

#Make sure an existing user name is provided or abort the request
def _validate_existing_user_name() -> None:
  user_name = _validate_user_name()

  if not users.exists(user_name):
    abort(404, 'NOT_FOUND,user_name')

  return user_name
