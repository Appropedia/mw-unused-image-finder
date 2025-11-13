from collections.abc import Callable
from flask import Blueprint, session, redirect, url_for, request, render_template, abort, flash, g
from modules.model.table import users

blueprint = Blueprint('session_control', __name__)

#Route handler for the login view
@blueprint.route('/login', methods = ['GET', 'POST'])
def login():
  if 'user_name' in session:
    return redirect(url_for('default.view'))

  match request.method:
    case 'GET':
      return render_template('view/login.jinja.html')
    case  'POST':
      #Make sure all form fields are provided
      if 'user_name' not in request.form or \
         'user_password' not in request.form:
        abort(400)

      #Authenticate the user now
      password_valid, user_status = users.authenticate(name = request.form['user_name'],
                                                       password = request.form['user_password'])

      if not password_valid:
        flash('Invalid user credentials.')
        return render_template('view/login.jinja.html')

      if user_status == 'banned':
        flash('Your account has been banned. Please contact your site administrator for details.')
        return render_template('view/login.jinja.html')

      #Set the session status to active and redirect to the default view
      session['user_name'] = request.form['user_name']
      return redirect(url_for('default.view'))

#Route handler for the logout action
@blueprint.route('/logout')
def logout():
  session.pop('user_name', None)
  return redirect(url_for('session_control.login'))

_route_handlers = []  #List of route handlers that require an active user session

#Function decorator for registering route handlers that require an active user session
def login_required(func: Callable):
  _route_handlers.append(func)
  return func

#Check for an active user session when a route handler is about to be called, redirecting to the
#login view when needed
def check(request_endpoint, route_handler: Callable):
  if route_handler not in _route_handlers:
    #The route handler doesnt require login, proceed with the request
    return

  if 'user_name' not in session:
    #Login required and user not logged in, redirect to login view
    return redirect(url_for('session_control.login'))

  #User is logged in, store user information in the global context
  g.user_id, g.user_status = users.read(session['user_name'])

  if g.user_status is None or g.user_status == 'banned':
    #Invalid or banned account, drop the session immediately
    session.pop('user_name', None)
    abort(401)

  if g.user_status == 'new_pass' and request_endpoint != 'password_update.view':
    #The account has a new generated password, prompt for password update
    return redirect(url_for('password_update.view'))
