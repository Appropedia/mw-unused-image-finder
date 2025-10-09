from flask import Blueprint, session, request, render_template, flash, redirect, url_for
from modules.controller import session_control
from modules.model import users
from modules.utility import password_rules

blueprint = Blueprint('password_update', __name__)

#Route handler for the password update view
@blueprint.route('/password_update', methods = ['GET', 'POST'])
@session_control.login_required
def view():
  match request.method:
    case 'GET':
      return render_template('password_update.html.jinja')
    case 'POST':
      #Make sure all form fields are provided
      if 'current_password' not in request.form or \
         'new_password' not in request.form or \
         'confirmed_password' not in request.form:
        abort(400)

      #Validate the password confirmation
      if request.form['new_password'] != request.form['confirmed_password']:
        flash('New passwords don\'t match. Try again.')
        return render_template('password_update.html.jinja')

      #Do a password rule check
      password_ok, password_message = password_rules.check(request.form['new_password'])
      if not password_ok:
        flash(password_message)
        return render_template('password_update.html.jinja')

      #Validate the current password
      password_valid = users.authenticate(name = session['user_name'],
                                          password = request.form['current_password'])[0]
      if not password_valid:
        flash('Current password is incorrect.')
        return render_template('password_update.html.jinja')

      #Perform the password change now
      users.update_password_and_status(session['user_name'], request.form['new_password'], 'active')

      flash('Your password has been updated.')
      return redirect(url_for('default.view'))
