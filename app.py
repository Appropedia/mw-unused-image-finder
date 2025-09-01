#!/usr/bin/env -S sh -c 'cd $(dirname $0); python/bin/python -m flask -A $(basename $0) $@'

from flask import Flask, render_template
from modules.common import config
from modules.model import db
from modules.mediawiki import cors_proxy

config.load('config.toml')

app = Flask(__name__, static_folder = 'assets')
app.register_blueprint(cors_proxy.blueprint)

@app.route('/')
def default_view():
  return render_template('main.html.jinja',
                         api = config.root.mediawiki_server.frontend_api())

@app.teardown_appcontext
def close_connection(exception):
  db.close()
