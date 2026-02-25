from flask import Blueprint, render_template
from modules.controller import session_control

blueprint = Blueprint('default', __name__)

#Route handler for the default view
@blueprint.get('/')
@session_control.login_required()
def get() -> str:
  return render_template('view/main.jinja.html')
