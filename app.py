#!/usr/bin/env -S sh -c 'cd $(dirname $0); python/bin/python -m flask -A $(basename $0) $@'

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from modules.common import config
from modules.mediawiki import cors_proxy
from modules.controller import main
from modules.controller.development import file_search, file_info
from modules.model import db

#Register module configurations
config.register({
  'reverse_proxy': {
    'enabled': False,
  },
})

#Load the configuration file. Do this only after importing every module so they've had a chance to
#register properly.
config.load('config.toml')

#Create the Flask application object and register all blueprints
app = Flask(__name__, static_folder = 'assets')
app.register_blueprint(cors_proxy.blueprint)
app.register_blueprint(main.blueprint)
app.register_blueprint(file_search.blueprint, url_prefix = '/development')
app.register_blueprint(file_info.blueprint, url_prefix = '/development')

#Configure jinja stripping
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

#Add the ProxyFix middleware if enabled
if config.root.reverse_proxy.enabled:
  app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

#Close the database connection (if open) after every application context is popped
@app.teardown_appcontext
def close_connection(exception):
  db.close()
