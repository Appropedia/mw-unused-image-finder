from datetime import datetime, timezone
from flask import Blueprint, abort, render_template
from modules.controller import session_control

blueprint = Blueprint('help_page', __name__)

#Route handler for the help page view
@blueprint.get('/help/<page>')
@session_control.login_required()
def view_get(page) -> str:
  #Make sure the requested help page is valid
  help_pages = ('wikitext',)

  if page not in help_pages:
    abort(404)

  #Prepare the render parameters and render the template
  render_params = {}

  if page in ('wikitext'):
    render_params['example_iso_time'] = datetime.now().astimezone(timezone.utc).\
                                        replace(microsecond=0).isoformat().replace('+00:00', 'Z')

  return render_template(f'view/{page}_help.jinja.html', **render_params)
