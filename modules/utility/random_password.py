import string, secrets

#Generate a random password for the flask server application that can be used for signing user
#session cookies and store it in the specified file
def generate_for_flask_session(secret_key_file: str):
  with open(secret_key_file, 'xb') as f:
    f.write(secrets.token_bytes())

#Generate a random password suitable for temporary use when creating or recovering a user account
def generate_for_user():
  #Define all valid characters for user passwords
  available_characters = string.ascii_lowercase + string.ascii_uppercase + string.digits +\
                         string.punctuation

  #Generate the random password with those characters
  return ''.join(secrets.choice(available_characters) for i in range(16))
