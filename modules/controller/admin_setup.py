from flask import Blueprint, abort, request, render_template, flash, redirect, url_for
from modules.model import users

blueprint = Blueprint('admin_setup', __name__)

#Route handler for the administrator account setup view
@blueprint.route('/admin_setup', methods = ['GET', 'POST'])
def view():
  if complete():
    #This is clearly a vulneration attempt - avoid it
    abort(403)

  match request.method:
    case 'GET':
      return render_template('admin_setup.html.jinja')
    case 'POST':
      #Make sure all form fields are provided
      if 'user_name' not in request.form or \
         'user_password' not in request.form or \
         'confirmed_password' not in request.form:
        abort(400)

      #Validate the password confirmation
      if request.form['user_password'] != request.form['confirmed_password']:
        flash('Password mismatch. Try again.')
        return render_template('admin_setup.html.jinja')

      #All checks passed, create the administrator account now
      users.create(name = request.form['user_name'],
                   password = request.form['user_password'],
                   status = 'active')

      #TODO: Add admin privileges to the user

      flash('Administrator account created.')
      return redirect(url_for('session_control.login'))

_admin_account_available = False   #Tells whether an administrator account is available

#Check whether an administrator account has already been registered
def complete():
  global _admin_account_available

  if not _admin_account_available:
    #Note: This is not the intended way to validate the existence of an administrator account. This
    #will be changed later.
    if users.total() > 0:
      _admin_account_available = True;

  return _admin_account_available
