from modules.model import db

#Schema initialization function
@db.schema
def init_schema() -> None:
  con = db.get()

  #This view allows to query for the id and position of all cleanup reasons linked to an specific
  #cleanup action
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'cleanup_action_choices_view(cleanup_action_name, cleanup_reason_id, cleanup_choice_position) '
    'AS SELECT cleanup_actions.name, cleanup_choices.cleanup_reason_id, cleanup_choices.position '
    'FROM cleanup_actions '
    'INNER JOIN cleanup_choices ON cleanup_actions.id = cleanup_choices.cleanup_action_id')

  #This view allows to query for all linked cleanup actions and cleanup reasons by their name
  con.execute(
    'CREATE VIEW IF NOT EXISTS '
    'cleanup_actions_reasons_view(cleanup_action_name, cleanup_action_desciption, '
    'cleanup_action_position, cleanup_choice_position, cleanup_reason_name, '
    'cleanup_reason_description) AS '
    'SELECT cleanup_actions.name, cleanup_actions.description, cleanup_actions.position, '
    'cleanup_choices.position, cleanup_reasons.name, cleanup_reasons.description '
    'FROM cleanup_actions '
    'INNER JOIN cleanup_choices ON cleanup_actions.id = cleanup_choices.cleanup_action_id '
    'INNER JOIN cleanup_reasons ON cleanup_reasons.id = cleanup_choices.cleanup_reason_id')

#Get the link status, name and description of all cleanup reasons with respect to a given cleanup
#action
def get_reasons_linked_to_action(cleanup_action_name: str) -> list[tuple[bool, str, str]]:
  cursor = db.get().execute(
    'SELECT linked_choices.cleanup_reason_id IS NOT NULL, cleanup_reasons.name, '
    'cleanup_reasons.description FROM cleanup_reasons LEFT JOIN '
      '(SELECT cleanup_reason_id, cleanup_choice_position FROM cleanup_action_choices_view '
      'WHERE cleanup_action_name = ?) AS linked_choices '
    'ON cleanup_reasons.id = linked_choices.cleanup_reason_id '
    'ORDER BY linked_choices.cleanup_choice_position ASC NULLS LAST',
    (cleanup_action_name,))
  cursor.row_factory = lambda cur, row: (bool(row[0]),) + row[1:]
  return cursor.fetchall()

#Get the names of all cleanup actions linked to a given cleanup reason
def get_actions_linked_to_reason(cleanup_reason_name: str) -> list[str]:
  cursor = db.get().execute(
    'SELECT cleanup_action_name FROM cleanup_actions_reasons_view WHERE cleanup_reason_name = ?',
    (cleanup_reason_name,))
  cursor.row_factory = lambda cur, row: row[0]
  return cursor.fetchall()

#Get the names and descriptions of all cleanup actions and reasons
def get_actions_and_reasons() -> list[dict[str, str | list[dict[str, str]]]]:
  con = db.get()

  #Get the names and descriptions of all distinct cleanup actions that are linked to reasons
  cursor = con.execute(
    'SELECT DISTINCT cleanup_action_name, cleanup_action_desciption '
    'FROM cleanup_actions_reasons_view ORDER BY cleanup_action_position ASC')

  cursor.row_factory = lambda cur, row: {
    'name': row[0],
    'description': row[1],
  }

  results = cursor.fetchall()

  #Get the names and descriptions of all reasons linked to every action
  for action in results:
    cursor = con.execute(
      'SELECT cleanup_reason_name, cleanup_reason_description FROM cleanup_actions_reasons_view '
      'WHERE cleanup_action_name = ? ORDER BY cleanup_choice_position ASC', (action['name'],))

    cursor.row_factory = lambda cur, row: {
      'name': row[0],
      'description': row[1],
    }

    action['cleanup_reasons'] = cursor.fetchall()

  return results
