import enum
from modules.model import db

#Enumeration of operation results
class Status(enum.Enum):
  SUCCESS          = enum.auto()
  INVALID_CATEGORY = enum.auto()

#Schema initialization function
@db.schema
def init_schema() -> None:
  con = db.get()

  con.execute(
    'CREATE TABLE IF NOT EXISTS wikitext('
      'name_ref TEXT NOT NULL, '
      'category TEXT NOT NULL, '
      'content TEXT NOT NULL, '
      'UNIQUE (name_ref, category))')

  #These triggers are used to cascade deletions from the cleanup action and cleanup reason tables
  con.execute(
    'CREATE TRIGGER IF NOT EXISTS wikitext_cascade_delete_cleanup_action '
    'AFTER DELETE ON cleanup_actions BEGIN '
    'DELETE FROM wikitext WHERE name_ref = \'cleanup_action:\' || OLD.id; END')

  con.execute(
    'CREATE TRIGGER IF NOT EXISTS wikitext_cascade_delete_cleanup_reason '
    'AFTER DELETE ON cleanup_reasons BEGIN '
    'DELETE FROM wikitext WHERE name_ref = \'cleanup_reason:\' || OLD.id; END')

#Create, update or delete a table row with the provided wikitext content
def _write(name_ref: str, category: str, content: str | None) -> Status:
  with db.get() as con:
    if content is None:
      con.execute(
        'DELETE FROM wikitext WHERE name_ref = ? AND category = ?', (name_ref, category))
    else:
      con.execute(
        'INSERT INTO wikitext (name_ref, category, content) '
        'VALUES (:name_ref, :category, :content) '
        'ON CONFLICT (name_ref, category) DO UPDATE SET content = :content',
        { 'name_ref': name_ref, 'category': category, 'content': content })

  return Status.SUCCESS

#Update the wikitext template
def write_template(content: str | None) -> Status:
  return _write('template', 'global', content)

#Update the wikitext for a cleanup action
def write_cleanup_action(cleanup_action_id: int, category: str, content: str | None) -> Status:
  if category not in ('individual', 'distinct', 'unanimous'):
    return Status.INVALID_CATEGORY

  return _write(f'cleanup_action:{cleanup_action_id}', category, content)

#Update the wikitext for a cleanup reason
def write_cleanup_reason(cleanup_reason_id: int, content: str | None) -> Status:
  return _write(f'cleanup_reason:{cleanup_reason_id}', 'distinct', content)

#Read the wikitext category and content from all table rows matching a given name reference
def _read(name_ref: str) -> list[dict[str, str]]:
  rows = db.get().execute(
    'SELECT category, content FROM wikitext WHERE name_ref = ?', (name_ref,)).fetchall()
  return { category: content for category, content in rows }

#Read the template wikitext
def read_template() -> str:
  result = _read('template')
  return result['global'] if result else ''

#Read the wikitext of the cleanup action for every category
def read_cleanup_action(cleanup_action_id: int) -> list[dict[str, str]]:
  result = _read(f'cleanup_action:{cleanup_action_id}')
  return { 'individual': '', 'distinct': '', 'unanimous': '' } | result

#Read the wikitext of the cleanup reason for every category
def read_cleanup_reason(cleanup_reason_id: int) -> str:
  result = _read(f'cleanup_reason:{cleanup_reason_id}')
  return result['distinct'] if result else ''
