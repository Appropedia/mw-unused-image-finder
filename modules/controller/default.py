from flask import Blueprint, request, render_template
from modules.model import db_views

blueprint = Blueprint('default', __name__)

#Route handler for the default view
@blueprint.route('/')
def view():
  search_output = do_search(request.args)

  return render_template('default.html.jinja',
                         **search_output)

#Perform an image search, if requested.
#Parameters:
# - args: Request arguments.
def do_search(args: dict) -> dict:
  #Parse parameters and provide defaults if applicable
  if 'usage' in args:
    match args['usage']:
      case 'unused': usage = db_views.Usage.unused
      case 'used':   usage = db_views.Usage.used
      case 'any':    usage = db_views.Usage.any
      case _:
        return {'message': f'Invalid request parameter: "usage={args['usage']}"'}
  else:
    return {}   #Parameter missing - don't treat as a search request

  if usage in (db_views.Usage.used, db_views.Usage.any):
    include_newest = 'incl_newest' in args
  else:
    include_newest = False

  if 'sort_by' in args:
    match args['sort_by']:
      case 'all_rev_size': sort_by = db_views.SortBy.all_rev_size
      case 'max_rev_size': sort_by = db_views.SortBy.max_rev_size
      case 'title':        sort_by = db_views.SortBy.title
      case 'timestamp':    sort_by = db_views.SortBy.timestamp
      case _:
        return {'message': f'Invalid request parameter: "sort_by={args['sort_by']}"'}
  else:
    sort_by = db_views.SortBy.all_rev_size

  if 'order' in args:
    match args['order']:
      case 'normal':
        if sort_by in (db_views.SortBy.title,): sort_order = db_views.SortOrder.asc
        else:                                   sort_order = db_views.SortOrder.desc
      case 'reverse':
        if sort_by in (db_views.SortBy.title,): sort_order = db_views.SortOrder.desc
        else:                                   sort_order = db_views.SortOrder.asc
      case _:
        return {'message': f'Invalid request parameter: "order={args['order']}"'}
  else:
    sort_order = db_views.SortOrder.asc

  #Request parameters validated. Perform the actual search in the database.
  return {'search_results': db_views.search_images(usage, include_newest, sort_by, sort_order)}
