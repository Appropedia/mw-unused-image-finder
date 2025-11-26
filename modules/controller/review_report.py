import textwrap, json, itertools
from flask import Blueprint, request, render_template, Response, abort
from modules.controller import session_control
from modules.model.table import users, cleanup_actions, cleanup_reasons
from modules.model.view import review_details

blueprint = Blueprint('review_report', __name__)

#Route handler for the review report view
@blueprint.route('/review_report')
@session_control.login_required
def view():
  #Create a dictionary with the available request filters and their valid values, if applicable
  available_filters = {
    'review_author':  { 'type': 'select', 'options': users.read_name_all() },
    'cleanup_action': { 'type': 'select', 'options': cleanup_actions.read_name_all() },
    'cleanup_reason': { 'type': 'select', 'options': cleanup_reasons.read_name_all() },
    'image_title':    { 'type': 'input' },
  }

  #Validate the filter request parameters
  _validate_filters(available_filters)

  #Gather the filter parameters from the request in a separate dictionary
  filter_params = { key: value for key, value in request.args.items() if key in available_filters }

  #Call the corresponding format handler
  match request.args.get('format'):
    case None:                return _read_html(available_filters, filter_params)
    case 'json':              return _read_json(filter_params)
    case 'csv':               return _read_csv(filter_params)
    case _ as invalid_format: abort(400, f'Unsupported download format: {invalid_format}')

#Render the report as an HTML page
def _read_html(available_filters: dict[str, str | list[str]], filter_params: dict[str, str]) -> str:
  #Validate and get the limit and offset request parameters
  limit, offset = _validate_request_range()

  #Gather the review report data
  reviews, more_results = review_details.get_range(limit, offset, filter_params)

  #Set the parameters and render the template
  render_params = {
    'limit': limit,
    'offset': offset,
    'more_results': more_results,
    'filter_params': filter_params,
    'available_filters': available_filters,
    'reviews': reviews,
  }

  return render_template('view/review_report.jinja.html', **render_params)

#Provide a downloadable auto-generated JSON document with the full report
def _read_json(filter_params: dict[str, str]) -> str:
  #This generator function is used to iterate over the database retrieving the report data in
  #blocks, this way the database isn't completely blocked during long transfers
  def json_format_generator():
    INDENT = 4      #Indentation depth in spaces

    yield '['       #Opening bracket for the full JSON report as an array

    #Iterate over blocks and then rows
    line_end = '\n'
    for block in review_details.get_bulk(filter_params):
      for row in block:
        #Indent and append the next record at the next line
        yield line_end + textwrap.indent(json.dumps(row, indent = INDENT), ' ' * INDENT)

        #Append a trailing comma to the previous line for any record that follows
        if line_end == '\n':
          line_end =  ',\n'

    yield '\n]\n'   #Final closing bracket

  #Return the downloadable data using the generator
  return Response(
    json_format_generator(),
    mimetype='application/json',
    headers={'Content-Disposition': 'attachment;filename=reviews.json'})

#Provide a downloadable auto-generated CSV document with the full report
def _read_csv(filter_params: dict[str, str]) -> str:
  #This generator function is used to iterate over the database retrieving the report data in
  #blocks, this way the database isn't completely blocked during long transfers
  def csv_format_generator():
    #Yield the table headers
    yield 'No., File, Revision, Action, Reason, Comments, Last update, Author, Author update time\n'

    #Iterate over blocks and then rows
    for block in review_details.get_bulk(filter_params):
      for num, row in enumerate(block, start = 1):
        #Format all the data in separate columns of different length, as the review can contain any
        #number of cleanup proposals and authors and each will need a separate row
        column_data = (
          (f'{num}',),
          (f'"{row['image_title']}"',),
          tuple(f'{sub_row['timestamp']}' for sub_row in row['cleanup_proposal']),
          tuple(f'"{sub_row['action']}"' for sub_row in row['cleanup_proposal']),
          tuple(f'"{sub_row['reason']}"' for sub_row in row['cleanup_proposal']),
          (f'"{row['comments'].replace('"', '""')}"',),
          (f'{row['update_time']}',),
          tuple(f'"{sub_row['user_name']}"' for sub_row in row['authors']),
          tuple(f'{sub_row['timestamp']}' for sub_row in row['authors']),
        )

        #Generate as many csv rows as the longest column per record, leaving empty csv columns where
        #the data runs out
        for columns in itertools.zip_longest(*column_data, fillvalue = ''):
          yield f'{','.join(columns)}\n'

  #Return the downloadable data using the generator
  return Response(
    csv_format_generator(),
    mimetype='text/csv',
    headers={'Content-Disposition': 'attachment;filename=reviews.csv'})

#Convert the limit and offset request arguments to integers, validate them, and provide defaults if
#absent
def _validate_request_range() -> tuple[int, int]:
  if 'limit' in request.args:
    try:
      limit = int(request.args['limit'])
    except ValueError:
      abort(400, 'Request parameter must be a number: limit')

    if limit <= 0:
      abort(400, 'Request parameter must be greater than 0: limit')
  else:
    limit = 50

  if 'offset' in request.args:
    try:
      offset = int(request.args['offset'])
    except ValueError:
      abort(400, 'Request parameter must be a number: offset')

    if offset < 0:
      abort(400, 'Request parameter must be greater than or equal to 0: offset')
  else:
    offset = 0

  return limit, offset

#Validate the filter request arguments if present, making sure they exist in the provided lists
def _validate_filters(filters: dict[str, list[str] | None]) -> None:
  for name, properties in filters.items():
    match properties['type']:
      case 'select':
        #Select filters must specify a valid option
        if name in request.args and request.args[name] not in properties['options']:
          abort(400, f'Invalid filter option for {name}: {request.args[name]}')
      case 'input':
        #Input filters can accept any text so no check is performed
        pass
      case _ as invalid_type:
        raise ValueError(f'Invalid filter type: {invalid_type}')
