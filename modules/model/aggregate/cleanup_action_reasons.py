import enum
from modules.utility.extend_enum import extend_enum
from modules.model import db
from modules.model.table import cleanup_actions, cleanup_reasons, cleanup_choices

#Enumeration of operation results (extends those from cleanup_choices)
@extend_enum(cleanup_choices.Status)
class Status(enum.Enum):
  NON_EXISTENT_ACTION = enum.auto()
  NON_EXISTENT_REASON = enum.auto()

#Create or delete an action/reason link based on the given valid choice status
def update(cleanup_action_name: str, cleanup_reason_name: str, valid_choice: bool) -> Status:
  #Obtain the IDs of the action/reason pair
  cleanup_action_id = cleanup_actions.read_id(cleanup_action_name)
  if cleanup_action_id is None: return Status.NON_EXISTENT_ACTION

  cleanup_reason_id = cleanup_reasons.read_id(cleanup_reason_name)
  if cleanup_reason_id is None: return Status.NON_EXISTENT_REASON

  #If the valid choice status is set attempt to create a new link, otherwise attempt to delete it
  if valid_choice:
    status = Status(cleanup_choices.create(cleanup_action_id, cleanup_reason_id).value)

    #If attempting to re-create an existing link return successfully, otherwise propagate the result
    return Status.SUCCESS if status == Status.LINK_CONFLICT else status
  else:
    status = Status(cleanup_choices.delete(cleanup_action_id, cleanup_reason_id).value)

    #If attempting to delete a non-existing link return successfully, otherwise propagate the result
    return Status.SUCCESS if status == Status.NON_EXISTENT_LINK else status

#Swap the position of an action/reason link it with the one next to it in the same action group
def swap(cleanup_action_name: str, cleanup_reason_name: str,
         direction: cleanup_choices.Direction) -> Status:
  #Obtain the IDs of the action/reason pair
  cleanup_action_id = cleanup_actions.read_id(cleanup_action_name)
  if cleanup_action_id is None: return Status.NON_EXISTENT_ACTION

  cleanup_reason_id = cleanup_reasons.read_id(cleanup_reason_name)
  if cleanup_reason_id is None: return Status.NON_EXISTENT_REASON

  #Perform the swap operation and propagate the result
  return Status(cleanup_choices.swap(cleanup_action_id, cleanup_reason_id, direction).value)
