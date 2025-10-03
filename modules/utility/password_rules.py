#Perform a rule check on a given password
def check(password: str) -> tuple[bool, str]:
  if len(password) < 8:
    return False, 'Password should be at least 8 characters long'

  return True, 'OK'
