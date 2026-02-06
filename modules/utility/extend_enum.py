from enum import Enum
from collections.abc import Callable

#Class decorator for extending an enum with another one
#Assumptions:
# - Both enums use enum.auto() for all of their member values, otherwise overlapped values or even
#   exceptions might arise
# - All enum member names are unique, otherwise wrong numbering might occur
def extend_enum(base_enum: Enum) -> Callable[[Enum], Enum]:
  def wrapper(extended_enum: Enum) -> Enum:
    #Collect all base and extended members in separate dictionaries, but offset the extended ones by
    #the amount of the bases ones
    base_members = { member.name: member.value for member in base_enum }
    extended_members = { member.name: member.value + len(base_enum) for member in extended_enum }

    #Return a new enum using the combined members
    return Enum(extended_enum.__name__, base_members | extended_members)

  return wrapper
