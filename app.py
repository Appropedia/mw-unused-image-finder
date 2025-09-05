#!/usr/bin/env -S sh -c 'cd $(dirname $0); python/bin/python -m flask -A $(basename $0) $@'

from flask import Flask
from modules.common import config
from modules.mediawiki import cors_proxy
from modules.controller import default
from modules.model import db

#Load the configuration file. Do this only after importing every module so they've had a chance to
#register properly.
config.load('config.toml')

#Create the Flask application object and register all blueprints
app = Flask(__name__, static_folder = 'assets')
app.register_blueprint(cors_proxy.blueprint)
app.register_blueprint(default.blueprint)

#Configure jinja stripping
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

#Close the database connection (if open) after every application context is popped
@app.teardown_appcontext
def close_connection(exception):
  db.close()
