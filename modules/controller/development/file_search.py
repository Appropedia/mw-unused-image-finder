from flask import Blueprint, request, render_template
from modules.model.view import image_usage

blueprint = Blueprint('file_search', __name__)

#Route handler for the file search view
@blueprint.route('/file_search')
def view():
  search_output = do_search(request.args)

  return render_template('development/file_search.html.jinja', **search_output)

#Perform an image search, if requested.
#Parameters:
# - args: Request arguments.
def do_search(args: dict) -> dict:
  QueryParams = image_usage.QueryParams

  #Parse parameters and provide defaults if applicable
  if 'usage' in args:
    match args['usage']:
      case 'unused': usage = QueryParams.Usage.unused
      case 'used':   usage = QueryParams.Usage.used
      case 'any':    usage = QueryParams.Usage.any
      case _:
        return {'message': f'Invalid request parameter: "usage={args['usage']}"'}
  else:
    return {}   #Parameter missing - don't treat as a search request

  if usage in (QueryParams.Usage.used, QueryParams.Usage.any):
    include_newest = 'incl_newest' in args
  else:
    include_newest = False

  if 'sort_by' in args:
    match args['sort_by']:
      case 'all_rev_size': sort_by = QueryParams.SortBy.all_rev_size
      case 'max_rev_size': sort_by = QueryParams.SortBy.max_rev_size
      case 'title':        sort_by = QueryParams.SortBy.title
      case 'timestamp':    sort_by = QueryParams.SortBy.timestamp
      case _:
        return {'message': f'Invalid request parameter: "sort_by={args['sort_by']}"'}
  else:
    sort_by = QueryParams.SortBy.all_rev_size

  if 'order' in args:
    match args['order']:
      case 'normal':
        if sort_by in (QueryParams.SortBy.title,): sort_order = QueryParams.SortOrder.asc
        else:                                      sort_order = QueryParams.SortOrder.desc
      case 'reverse':
        if sort_by in (QueryParams.SortBy.title,): sort_order = QueryParams.SortOrder.desc
        else:                                      sort_order = QueryParams.SortOrder.asc
      case _:
        return {'message': f'Invalid request parameter: "order={args['order']}"'}
  else:
    sort_order = QueryParams.SortOrder.asc

  #Request parameters validated. Perform the actual search in the database.
  return {'search_results': image_usage.search(usage, include_newest, sort_by, sort_order)}
