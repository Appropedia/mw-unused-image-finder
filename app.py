#!/usr/bin/env -S sh -c 'cd $(dirname $0); python/bin/python -m flask -A $(basename $0) $@'

from flask import Flask, render_template
from modules.common import config

config.load('config.toml')

app = Flask(__name__, static_folder = 'assets')

@app.route("/")
def default_view():
  return render_template('login.html.jinja')
