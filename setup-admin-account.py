#!/usr/bin/env -S sh -c 'cd $(dirname $0); python/bin/python -m $(basename ${0%.py}) $@'

from getpass import getpass
from modules.common import config
from modules.model import db
from modules.model.table import users, privileges
from modules.model.view import user_privileges
from modules.utility import random_password, password_rules

config.load('config.toml', warn_unknown = False)

db.go_without_flask()

#Check for previous admin accounts and ask for confirmation if any
prev_admin_user_names = user_privileges.get_administrator_names()
if len(prev_admin_user_names) > 0:
  print('The following accounts are registered with administrator privileges already:')
  print('\n'.join(f' - {user_name}' for user_name in prev_admin_user_names))
  print('In case of password loss you can regenerate it for any of those accounts with the '
        'regenerate_user_password script.')
  confirmation = input('Proceed to create a new account? (yes/no) ')
  if confirmation != 'yes':
    exit()

#Input and validate user name
user_name = input('User name for the new administrator account: ')

if len(user_name) == 0:
  print('No user name provided')
  exit()

#Check for user name availability
if not users.name_available(user_name):
  print('A user under that name exists already')
  exit()

#Input and generate or validate password
user_password = getpass(f'Password for {user_name} (leave empty for random): ')

if user_password == '':
  user_password = random_password.generate_for_user()
  password_is_random = True
else:
  password_verify = getpass(f'Verify password: ')
  if user_password != password_verify:
    print('Password mismatch. Try again please.')
    exit()
  password_is_random = False

#Perform a password rule check
validity_status = password_rules.check(user_password)
if validity_status != password_rules.Status.OK:
  print(validity_status.value)
  exit()

#Perform account creation now
user_id = users.create(user_name, user_password, 'new_pass' if password_is_random else 'active')
privileges.create(user_id, 'admin')
privileges.create(user_id, 'plan')
privileges.create(user_id, 'review')

print(f'Account created for {user_name}'
      f'{f' with password {user_password}' if password_is_random else ''}')
