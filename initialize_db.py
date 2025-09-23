#!/usr/bin/env -S sh -c 'cd $(dirname $0); python/bin/python -m $(basename ${0%.py}) $@'

import secrets
from modules.common import config
from modules.common import app_config
from modules.model import db
from modules.model import images
from modules.model import revisions
from modules.model import hashes
from modules.model import unused_images
from modules.model import users
from modules.model.view import pending_hashes
from modules.model.view import image_usage
from modules.model.view import similar_images

config.load('config.toml', warn_unknown = False)

db.go_without_flask()
db.initialize_schema()
db.close()

try:
  with open(config.root.security.flask_secret_key_file, 'xb') as f:
    f.write(secrets.token_bytes())
except FileExistsError:
  print('Flask secret key file created already')
