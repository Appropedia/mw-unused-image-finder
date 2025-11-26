from flask import Flask
from markupsafe import Markup, escape

#Register every filter defined in this module
def register(app: Flask) -> None:
  app.jinja_env.filters['new_line_to_break'] = _new_line_to_break

#This filter safely prepends every line break in the string with an HTML <br> tag, so it preserves
#its line breaks when rendered in HTML
def _new_line_to_break(value: str) -> Markup:
  #Escape the string first so that any unsafe character is removed, then convert to string and
  #perform replacements, finally mark the string as safe
  return Markup(str(escape(value)).replace('\n', '<br>\n'))
