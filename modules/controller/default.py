from flask import Blueprint, render_template
from modules.controller import session_control

blueprint = Blueprint('default', __name__)

#Route handler for the default view
@blueprint.route('/')
@session_control.login_required
def view():
  return render_template('main.html.jinja')
