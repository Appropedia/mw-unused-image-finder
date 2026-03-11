#This file needs to exist in a directory visible to apache (e.g "/var/www/html"). Copy this to a
#location according your system configuration.

#It's likely that python won't find the main application module called "app" (app.py) by itself.
#Make sure to adjust python's search path for this purpose. You can do this by setting the
#PYTHONPATH environment variable to point to the repository or directly here by modifying sys.path,
#like this:
# import sys
# sys.path.insert(0, '/path/to/repository')

from urllib.parse import unquote
from app import app

#This application wrapper decodes all URLs before processing requests, as Flask expects them this
#way but Phusion Passenger doesn't do that.
def application(environ, start_response):
  if 'PATH_INFO' in environ:
    environ['PATH_INFO'] = unquote(environ['PATH_INFO'])

  return app(environ, start_response)
