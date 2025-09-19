from flask import Blueprint, render_template

blueprint = Blueprint('main', __name__)

#Route handler for the main view
@blueprint.route('/')
def view():
  return render_template('main.html.jinja')
