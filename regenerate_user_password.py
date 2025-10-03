#!/usr/bin/env -S sh -c 'cd $(dirname $0); python/bin/python -m $(basename ${0%.py}) $@'

from argparse import ArgumentParser
from modules.common import config
from modules.model import db, users
from modules.utility import random_password, password_rules

config.load('config.toml', warn_unknown = False)

db.go_without_flask()

#Register and parse arguments
parser = ArgumentParser()
parser.add_argument('user_name')
args = parser.parse_args()

#Generate a new password
new_password = random_password.generate_for_user()

#This is just for the sake of data integrity, just in case the password rules are ever changed
password_ok, password_message = password_rules.check(new_password)
if not password_ok:
  print(password_message)
  exit()

#Update the password and status
if users.update_password_and_status(args.user_name, new_password, 'new_pass'):
  print(f'New password generated for {args.user_name}: {new_password}')
else:
  print(f'No such user: {args.user_name}')
