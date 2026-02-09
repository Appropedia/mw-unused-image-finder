from collections.abc import Callable, Iterable
import re
from modules.model.table import cleanup_actions, cleanup_reasons, wikitext as wikitext_table
from modules.model.view import review_details
from modules.mediawiki_bot.wikitext_lexeme import lexeme_callback

#Dictionary for exported lexemes
parser_functions = {}

#Conditionally generate the specified section texts in order of appearance, applying special
#conditions
@lexeme_callback(parser_functions, 'reviewsections')
def _reviewsections(context: dict[str, any], *args: str):
  #Make sure enough arguments are given
  if len(args) < 3:
    return ''

  #Strip the arguments and get the default separator if not provided
  args = tuple(a.strip() for a in args)
  separator = _default_separator_if_absent(0, *args)

  #Get the cleanup proposal information
  _get_cleanup_proposal(context)

  #Iterate over the arguments in pairs
  result = []
  for cond, text in zip(args[1::2], args[2::2]):
    #Skip empty text arguments
    if not text: continue

    #Check the condition and append the text to the result if fulfilled
    match cond:
      case 'UNANIMOUSACTION':
        if _unanimous_cleanup_actions(context):
          result.append(text)
      case 'MULTIPLEACTIONS':
        if _multiple_cleanup_actions(context):
          result.append(text)
      case 'UNCONDITIONAL':
        result.append(text)

  #Join all results using the separator
  return separator.join(result)

#Iterate over the individual actions for each of the revisions in the review and return the
#specified text, expanding any tokens in it
@lexeme_callback(parser_functions, 'individualactions')
def _individualactions(context: dict[str, any], *args: str):
  #Make sure enough arguments are given
  if len(args) < 1:
    return ''

  #Strip the arguments and get the default separator if not provided
  args = tuple(a.strip() for a in args)
  separator = _default_separator_if_absent(1, *args)

  #Get the cleanup proposal information
  _get_cleanup_proposal(context)

  #Iterate over the individual actions
  result = []
  for revision_review in context['cleanup_proposal']:
    individual_action = revision_review['cleanup_action_name']
    individual_reason = revision_review['cleanup_reason_name']

    #Callback for substituting the %%TEXT%% token with the individual action wikitext
    def replace_text(matchobj: re.Match):
      _get_cleanup_action_wikitext(context, individual_action)
      return context['cleanup_action_wikitext'][individual_action]['individual']

    #Token substitution dictionary for other tokens
    keywords = {
      '%%REVISIONTIMESTAMP%%': revision_review['revision_timestamp'],
      '%%ACTIONNAME%%': individual_action,
      '%%REASONNAME%%': individual_reason,
      '%%ACTIONDESCRIPTION%%': lambda: cleanup_actions.read_description(individual_action),
      '%%REASONDESCRIPTION%%': lambda: cleanup_reasons.read_description(individual_reason),
    }

    #Replace all occurences of the %%TEXT%% token first, so that any other contained token can be
    #replaced afterwards
    iteration_result = re.sub('%%TEXT%%', replace_text, args[0].strip())

    #Replace all occurrences of other tokens now
    iteration_result = re.sub('%%[A-Z]+%%', _replace_function(keywords), iteration_result)

    result.append(iteration_result)

  #Join all results using the separator
  return separator.join(result)

#Iterate over the distinct actions in a review and return the specified text, expanding any tokens
#in it
@lexeme_callback(parser_functions, 'distinctactions')
def _distinctactions(context: dict[str, any], *args: str):
  #Make sure enough arguments are given
  if len(args) < 1:
    return ''

  #Strip the arguments and get the default separator if not provided
  args = tuple(a.strip() for a in args)
  separator = _default_separator_if_absent(1, *args)

  #Get the cleanup proposal information
  _get_cleanup_proposal(context)

  #Iterate over the distinct actions
  result = []
  for distinct_action in _unique(r['cleanup_action_name'] for r in context['cleanup_proposal']):
    #Callback for substituting the %%TEXT%% token with the distinct action wikitext
    def replace_text(matchobj: re.Match):
      _get_cleanup_action_wikitext(context, distinct_action)
      return context['cleanup_action_wikitext'][distinct_action]['distinct']

    #Token substitution dictionary for other tokens
    keywords = {
      '%%ACTIONNAME%%': distinct_action,
      '%%ACTIONDESCRIPTION%%': lambda: cleanup_actions.read_description(distinct_action),
    }

    #Replace all occurences of the %%TEXT%% token first, so that any other contained token can be
    #replaced afterwards
    iteration_result = re.sub('%%TEXT%%', replace_text, args[0].strip())

    #Replace all occurrences of other tokens now
    iteration_result = re.sub('%%[A-Z]+%%', _replace_function(keywords), iteration_result)

    result.append(iteration_result)

  #Join all results using the separator
  return separator.join(result)

#Return the specified text only if every single action in the review is the same, expanding any
#tokens in it
@lexeme_callback(parser_functions, 'unanimousaction')
def _unanimousaction(context: dict[str, any], *args: str):
  #Make sure enough arguments are given
  if len(args) < 1:
    return ''

  #Get the cleanup proposal information
  _get_cleanup_proposal(context)

  #Make sure the cleanup actions are unanimous
  if not _unanimous_cleanup_actions(context):
    return ''

  #Get the name of the unanimous action (prefer index 0 in case of unique image revision)
  unanimous_action = context['cleanup_proposal'][0]['cleanup_action_name']

  #Callback for substituting the %%TEXT%% token with the unanimous action wikitext
  def replace_text(matchobj: re.Match):
    _get_cleanup_action_wikitext(context, unanimous_action)
    return context['cleanup_action_wikitext'][unanimous_action]['unanimous']

  #Token substitution dictionary for other tokens
  keywords = {
    '%%ACTIONNAME%%': unanimous_action,
    '%%ACTIONDESCRIPTION%%': lambda: cleanup_actions.read_description(unanimous_action),
    '%%REASONNAMES%%': ', '.join(_unique(r['cleanup_reason_name']
                                         for r in context['cleanup_proposal'])),
  }

  #Replace all occurences of the %%TEXT%% token first, so that any other contained token can be
  #replaced afterwards
  result = re.sub('%%TEXT%%', replace_text, args[0].strip())

  #Replace all occurrences of other tokens now
  result = re.sub('%%[A-Z]+%%', _replace_function(keywords), result)

  return result

#Iterate over the distinct reasons in a review and return the specified text, expanding any tokens
#in it
@lexeme_callback(parser_functions, 'distinctreasons')
def _distinctreasons(context: dict[str, any], *args: str):
  #Make sure enough arguments are given
  if len(args) < 1:
    return ''

  #Strip the arguments and get the default separator if not provided
  args = tuple(a.strip() for a in args)
  separator = _default_separator_if_absent(1, *args)

  #Get the cleanup proposal information
  _get_cleanup_proposal(context)

  #Iterate over the distinct reasons
  result = []
  for distinct_reason in _unique(r['cleanup_reason_name'] for r in context['cleanup_proposal']):
    #Callback for substituting the %%TEXT%% token with the distinct reason wikitext
    def replace_text(matchobj: re.Match):
      _get_cleanup_reason_wikitext(context, distinct_reason)
      return context['cleanup_reason_wikitext'][distinct_reason]

    #Token substitution dictionary for other tokens
    keywords = {
      '%%REASONNAME%%': distinct_reason,
      '%%REASONDESCRIPTION%%': lambda: cleanup_reasons.read_description(distinct_reason),
    }

    #Replace all occurences of the %%TEXT%% token first, so that any other contained token can be
    #replaced afterwards
    iteration_result = re.sub('%%TEXT%%', replace_text, args[0].strip())

    #Replace all occurrences of other tokens now
    iteration_result = re.sub('%%[A-Z]+%%', _replace_function(keywords), iteration_result)

    result.append(iteration_result)

  #Join all results using the separator
  return separator.join(result)

#Filter duplicates from an iterable returning strings while keeping order of first appearance
def _unique(iterable: Iterable[str]) -> list[str]:
  return list(dict.fromkeys(iterable))

#Return the separator from the specified index in the arguments tuple if present and non-empty, or
#the default one otherwise
def _default_separator_if_absent(index: int, *args: str) -> str:
  return args[index] if index < len(args) and args[index] else '<br>\n'

#Get the details of every revision review and put them in the context dictionary
def _get_cleanup_proposal(context: dict[str, any]) -> None:
  #Avoid frequent database lookups
  if 'cleanup_proposal' in context:
    return

  context['cleanup_proposal'] = review_details.get_cleanup_proposal(context['image_review_id'])

#Function factory for creating regex substitution handlers that work with a dictionary
def _replace_function(keywords: dict[str, Callable[[], str] | str]) -> Callable[[re.Match], str]:
  def callback(matchobj: re.Match) -> str:
    #Use the text of the entire match to look up the substitution dictionary
    matched_text = matchobj.group()
    match keywords.get(matched_text):
      case str() as string:
        #Strings are returned directly
        return string
      case Callable() as func:
        #Callables are called first to get the returned string
        return func()
      case _:
        #Matched text is not in dictionary or an unsupported data type was provided, return the
        #matched text without any modification
        return matched_text

  return callback

#Get the wikitext of all categories of a given cleanup action and put them in the context dictionary
def _get_cleanup_action_wikitext(context: dict[str, any], cleanup_action_name: str) -> None:
  #Avoid frequent database lookups
  if ('cleanup_action_wikitext' in context and
      cleanup_action_name in context['cleanup_action_wikitext']):
    return

  #Initialize the sub dictionary if needed
  if 'cleanup_action_wikitext' not in context:
    context['cleanup_action_wikitext'] = {}

  context['cleanup_action_wikitext'][cleanup_action_name] = \
    wikitext_table.read_cleanup_action(cleanup_actions.read_id(cleanup_action_name))

#Get the wikitext of all categories of a given cleanup reason and put them in the context dictionary
def _get_cleanup_reason_wikitext(context: dict[str, any], cleanup_reason_name: str) -> None:
  #Avoid frequent database lookups
  if ('cleanup_reason_wikitext' in context and
      cleanup_reason_name in context['cleanup_reason_wikitext']):
    return

  #Initialize the sub dictionary if needed
  if 'cleanup_reason_wikitext' not in context:
    context['cleanup_reason_wikitext'] = {}

  context['cleanup_reason_wikitext'][cleanup_reason_name] = \
    wikitext_table.read_cleanup_reason(cleanup_reasons.read_id(cleanup_reason_name))

#Tell if the same action is selected for every image revision in the image review
def _unanimous_cleanup_actions(context: dict[str, any]) -> bool:
  #Get the cleanup proposal information and make sure at least one image revision is covered
  _get_cleanup_proposal(context)

  if len(context['cleanup_proposal']) < 1:
    return False

  #Check whether the cleanup action is unanimous by comparing the first proposal to the others
  return all(context['cleanup_proposal'][0]['cleanup_action_name'] ==
             r['cleanup_action_name'] for r in context['cleanup_proposal'][1:])

#Tell if more than one distinct action is selected for the revisions in the review
def _multiple_cleanup_actions(context: dict[str, any]) -> bool:
  #Get the cleanup proposal information and make sure at least two image revisions are covered
  _get_cleanup_proposal(context)

  if len(context['cleanup_proposal']) < 2:
    return False

  #Check whether there is at least two different cleanup actions by comparing the first proposal to
  #the others
  return any(context['cleanup_proposal'][0]['cleanup_action_name'] !=
             r['cleanup_action_name'] for r in context['cleanup_proposal'][1:])
