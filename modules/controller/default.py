from flask import Blueprint, render_template
from modules.controller import session_control
from modules.model.view import image_usage

blueprint = Blueprint('default', __name__)

#Route handler for the default view
@blueprint.get('/')
@session_control.login_required()
def get() -> str:
  render_params = image_usage.get_unreviewed_image_totals()
  return render_template('view/main.jinja.html', **render_params)
