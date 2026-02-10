import enum

#Enumeration of password check results
class Status(enum.Enum):
  OK        = ''
  TOO_SHORT = 'Password should be at least 8 characters long'

#Perform a rule check on a given password
def check(password: str) -> Status:
  if len(password) < 8:
    return Status.TOO_SHORT

  return Status.OK
