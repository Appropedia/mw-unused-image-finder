#!/usr/bin/env -S sh -c 'cd $(dirname $0); python/bin/python -m $(basename ${0%.py}) $@'

from modules.common import config
from modules.model import db
from modules.model.table import images
from modules.model.table import revisions
from modules.model.table import hashes
from modules.model.table import unused_images
from modules.model.table import users
from modules.model.table import privileges
from modules.model.table import image_concessions
from modules.model.table import cleanup_actions
from modules.model.table import cleanup_reasons
from modules.model.table import cleanup_choices
from modules.model.table import image_reviews
from modules.model.table import review_authors
from modules.model.table import revision_reviews
from modules.model.view import pending_hashes
from modules.model.view import image_usage
from modules.model.view import similar_images
from modules.model.view import image_revisions
from modules.model.view import user_privileges
from modules.model.view import cleanup_action_reason_links
from modules.model.view import review_details

config.load('config.toml', warn_unknown = False)

db.go_without_flask()
db.initialize_schema()
db.close()
