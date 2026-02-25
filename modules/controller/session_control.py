from collections.abc import Callable
from flask import Blueprint, session, redirect, url_for, request, render_template, abort, flash, g
from modules.model.table import users, privileges
from modules.model.view import user_privileges

blueprint = Blueprint('session_control', __name__)

#Route handler for the login view
@blueprint.get('/login')
def login_get():
  if 'user_name' in session:
    return redirect(url_for('default.get'))

  return render_template('view/login.jinja.html')

#Route handler for login requests
@blueprint.post('/login')
def login_post():
  #Make sure all form fields are provided
  if 'user_name' not in request.form or 'user_password' not in request.form:
    abort(400)

  #Authenticate the user now
  password_valid, ban_status = users.authenticate(name = request.form['user_name'],
                                                  password = request.form['user_password'])

  if not password_valid:
    flash('Invalid user credentials.')
    return render_template('view/login.jinja.html')

  if ban_status:
    flash('Your account has been banned. Please contact your site administrator for details.')
    return render_template('view/login.jinja.html')

  #Set the session status to active and redirect to the default view
  session['user_name'] = request.form['user_name']
  return redirect(url_for('default.get'))

#Route handler for the logout action
@blueprint.get('/logout')
def logout_get():
  session.pop('user_name', None)
  return redirect(url_for('session_control.login_get'))

_route_handler_privileges = {}  #Dictionary of user privileges required by each route handler

#Function decorator for registering route handlers that require an active user session with specific
#user privileges
def login_required(*required_privileges: str) -> Callable:
  #Make sure every privilege is valid
  invalid_privileges = tuple(p for p in required_privileges if p not in privileges.VALID_PRIVILEGES)
  if invalid_privileges:
    raise ValueError(f'Invalid privilege: "{invalid_privileges[0]}"')

  def wrapper(route_handler: Callable):
    _route_handler_privileges[route_handler] = required_privileges
    return route_handler

  return wrapper

#Check for an active user session when a route handler is about to be called, enforcing required
#privileges and redirecting to the login view when needed
def check(request_endpoint, route_handler: Callable):
  if route_handler not in _route_handler_privileges:
    #The route handler doesnt require login, proceed with the request
    return

  #The route handler requires login, make sure the user has a valid session
  if 'user_name' not in session:
    if request.method == 'GET':
      #No valid session while attempting to 'GET' the view, redirect to the login view instead
      return redirect(url_for('session_control.login_get'))
    else:
      #Forbid any other method
      abort(401)

  #User is logged in, store the user id in the global context
  g.user_id, password_reset, ban_status = users.read_id_status(session['user_name'])

  if g.user_id is None or ban_status:
    #Invalid or banned account, drop the session immediately
    session.pop('user_name', None)
    abort(401)

  #Also store the user privileges in the global context
  g.user_privileges = user_privileges.get(session['user_name'])

  #Make sure the user has all the privileges required by the route handler (if any)
  if any(p not in g.user_privileges for p in _route_handler_privileges[route_handler]):
    abort(403)

  if password_reset:
    #The account has a new generated password, prompt for password update
    if request_endpoint not in ('user_management.password_update_get',
                                'user_management.user_password_udpate_patch'):
      return redirect(url_for('user_management.password_update_get'))
    else:
      g.user_password_reset = True
