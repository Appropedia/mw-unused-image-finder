from werkzeug.exceptions import HTTPException
from flask import Blueprint, request, render_template, abort
from modules.controller import session_control
from modules.model.table import wikitext as wikitext_table

blueprint = Blueprint('wikitext_template', __name__)

#Field size limits
WIKITEXT_MAX_LEN = 1024

#Route handler for the wikitext template view
@blueprint.route('/wikitext_template', methods = ['GET', 'PATCH'])
@session_control.login_required
def handler() -> str:
  #Call the corresponding method handler
  match request.method:
    case 'GET':  return _read()
    case 'PATCH': return _update()

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

#Read method handler for the wikitext template view
def _read() -> str:
  #Prepare the render parameters and render the template
  render_params = {
    'WIKITEXT_MAX_LEN': WIKITEXT_MAX_LEN,
    'wikitext': wikitext_table.read_template(),
  }

  return render_template('view/wikitext_template.jinja.html', **render_params)

#Process a wikitext template write request
def _update() -> str:
  _validate_wikitext()
  wikitext = request.form['wikitext']
  status = wikitext_table.write_template(wikitext if wikitext != '' else None)
  return _handle_wikitext_table_return_status(status)

#Make sure the wikitext query parameters are valid or abort the request
def _validate_wikitext() -> None:
  if 'wikitext' not in request.form:
    abort(400, 'MISSING_FIELD,wikitext')
  if len(request.form['wikitext']) > WIKITEXT_MAX_LEN:
    abort(400, 'FIELD_TOO_LONG,wikitext')

#Handle the return status of a wikitext table module call, returning either 200 - 'OK' or a
#simplified error message accompanied by the corresponding HTTP error code
def _handle_wikitext_table_return_status(status: wikitext_table.Status) -> str:
  match status:
    case wikitext_table.Status.SUCCESS:
      return 'OK'
    case wikitext_table.Status.INVALID_CATEGORY:
      abort(404, 'NOT_FOUND,category')
