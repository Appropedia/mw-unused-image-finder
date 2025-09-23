#!/usr/bin/env -S sh -c 'cd $(dirname $0); python/bin/python -m flask -A $(basename $0) $@'

from flask import Flask, request
from werkzeug.middleware.proxy_fix import ProxyFix
from modules.common import config, app_config
from modules.mediawiki import cors_proxy
from modules.controller import default, session_control, admin_setup
from modules.controller.development import file_search, file_info
from modules.model import db

#Load the configuration file. Do this only after importing every module so they've had a chance to
#register properly.
config.load('config.toml')

#Create the Flask application object and register all blueprints
app = Flask(__name__, static_folder = 'assets')
app.register_blueprint(cors_proxy.blueprint)
app.register_blueprint(default.blueprint)
app.register_blueprint(session_control.blueprint)
app.register_blueprint(admin_setup.blueprint)
app.register_blueprint(file_search.blueprint, url_prefix = '/development')
app.register_blueprint(file_info.blueprint, url_prefix = '/development')

#Load the flask secrey key file
with open(config.root.security.flask_secret_key_file, 'rb') as f:
  app.secret_key = f.read()

#Configure jinja stripping
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

#Add the ProxyFix middleware if enabled
if config.root.reverse_proxy.enabled:
  app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

@app.before_request
def session_check():
  if request.endpoint in app.view_functions:
    return session_control.check(app.view_functions[request.endpoint])

#Close the database connection (if open) after every application context is popped
@app.teardown_appcontext
def close_connection(exception):
  db.close()
