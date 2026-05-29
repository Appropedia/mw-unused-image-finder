from flask import Blueprint, render_template
from modules.controller import session_control
from modules.model.view import unreviewed_images

blueprint = Blueprint('default', __name__)

#Route handler for the default view
@blueprint.get('/')
@session_control.login_required()
def get() -> str:
  unreviewed_image_totals = unreviewed_images.get_totals()

  #Compute review count and progress for the different categories
  review_params = {
    category: {
      'reviewed': totals['total'] - totals['unreviewed'],
    } for category, totals in unreviewed_image_totals.items()
  }

  return render_template('view/main.jinja.html', **(review_params))
