#!/usr/bin/env -S sh -c 'cd $(dirname $0); python/bin/python -m $(basename ${0%.py}) $@'

from modules.common import config
from modules.model import db

config.load('config.toml')

db.go_without_flask()
db.initialize_schema()
db.close()
