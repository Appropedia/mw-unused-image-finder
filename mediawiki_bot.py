#!/usr/bin/env -S sh -c 'cd $(dirname $0); python/bin/python -m $(basename ${0%.py}) $@'

import re
from modules.common import config
from modules.model import db
from modules.model.table import wikitext as wikitext_table
from modules.model.view import review_details
from modules.utility.wikitext_evaluator import evaluate
from modules.mediawiki_bot import api_client
from modules.mediawiki_bot.magic_words import magic_words
from modules.mediawiki_bot.parser_functions import parser_functions

#Register module configurations
config.register({
  'mediawiki_bot': {
    'username': '',
    'password': '',
  },
})

config.load('config.toml', warn_unknown = False)
db.go_without_flask()

#Insert the evaluated wikitext from a review into an article, removing any old version of the review
#and cleaning any dangling markers
def update_article_wikitext(article_wikitext: str, review_wikitext: str) -> str:
  START_MARKER = '<!-- Start: CleanupAssistantBot -->'
  END_MARKER = '<!-- End: CleanupAssistantBot -->'

  START_MARKER_RE = re.escape(START_MARKER)
  END_MARKER_RE = re.escape(END_MARKER)
  BREAK_RE = '\\n?\\n?'

  #This function deals with potential corruption situations such as duplicated review wikitext and
  #unmatched start and end markers by doing the following:
  # - Scan the wikitext for matched start and end markers and delete all content inside. If multiple
  #   consecutive start markers are found group them until an end marker is found before deletion
  #   (first deletion step).
  # - Remove any dangling start and end markers without removing anything else afterwards (second
  #   deletion step).

  #Variables used track the last deletion position and character deletion count. Both are used to
  #calculate the insertion position of the new wikitext so that it matches the position of the last
  #deleted review wikitext (if any). This way if a user edits a file page with an existing review
  #wikitext, it will keep its relative position after updating.
  last_del_pos = None
  char_del_count = 0

  #This callback for re.sub deletes all matches while tracking the position of the last deletion
  def tracking_cleaner_callback(matchobj: re.Match) -> str:
    nonlocal last_del_pos, char_del_count
    last_del_pos = matchobj.end(0)
    char_del_count += matchobj.end(0) - matchobj.start(0)
    return ''

  #Perform the first deletion step by removing content between matched start and end markers
  article_wikitext = re.sub(START_MARKER_RE + '[\\s\\S]*?' + END_MARKER_RE + BREAK_RE,
                            tracking_cleaner_callback, article_wikitext)

  #Calculate the preliminary insertion position after the first deletion step if any deletion was
  #made, then reset the character deletion count for the second one
  insert_pos = last_del_pos - char_del_count if last_del_pos is not None else None
  char_del_count = 0

  #This callback for re.sub deletes all matches while tracking deleted characters before the
  #insertion position
  def sliding_cleaner_callback(matchobj: re.Match) -> str:
    nonlocal char_del_count
    if insert_pos is not None and matchobj.end(0) <= insert_pos:
      char_del_count += matchobj.end(0) - matchobj.start(0)
    return ''

  #Perform the second deletion step by removing dangling start and end markers
  article_wikitext = re.sub(START_MARKER_RE + BREAK_RE, sliding_cleaner_callback, article_wikitext)
  article_wikitext = re.sub(END_MARKER_RE + BREAK_RE, sliding_cleaner_callback, article_wikitext)

  #Calculate the final insertion position after the second deletion step
  if insert_pos is not None:
    insert_pos -= char_del_count
  else:
    insert_pos = len(article_wikitext)  #No deletions made so will append instead

  #Split the article in two portions: one before the insertion position and another one after it
  left_portion = article_wikitext[:insert_pos]
  right_portion = article_wikitext[insert_pos:]

  #Create the final result by assembling the portions of the article with the review wikitext,
  #inserting line endings where needed
  result = left_portion

  if len(left_portion) >= 1 and left_portion[-1] != '\n':
    #Left portion doesn't end with a line break, append two
    result += '\n\n'
  elif len(left_portion) >= 2 and left_portion[-2] != '\n':
    #Left portion doesn't end with a double line break, append one
    result += '\n'

  result += START_MARKER + '\n' + review_wikitext + '\n' + END_MARKER

  if len(right_portion) >= 1 and right_portion[0] != '\n':
    #Right portion doesn't start with a line break, prepend two
    result += '\n\n'
  elif len(right_portion) >= 2 and right_portion[1] != '\n':
    #Right portion doesn't start with a double line break, prepend one
    result += '\n'

  result += right_portion

  return result

#Make sure credentials are defined or exit silently
if config.root.mediawiki_bot.username == '' or config.root.mediawiki_bot.password == '':
  exit(0)

#Log into the wiki server
session_cookie, csrf_token = api_client.login(config.root.mediawiki_bot.username,
                                              config.root.mediawiki_bot.password)

#Load the bot template or exit silently if not defined
bot_template = wikitext_table.read_template()

if not bot_template:
  exit(0)

#Create a wikitext lexicon dictionary from the loaded modules
lexicon = {
  'magic_words': magic_words,
  'parser_functions': parser_functions,
}

#Update each review pending synchronization
for image_review in review_details.get_pending_sync_reviews():
  #Set a new context for each review (deletes any data added by wikitext lexeme callbacks from
  #previous iterations)
  lexicon['context'] = {
    'image_review_id': image_review['id'],
    'timestamp': image_review['timestamp'],
    'comments': image_review['comments'],
    'author': image_review['author'],
  }

  #Evaluate the bot template using the contextualized lexicon to genrate the review wikitext
  review_wikitext = evaluate(bot_template, lexicon)

  #Read the current article contents from the wiki, udpate them with the review wikitext and store
  #them back to the wiki
  article_wikitext = api_client.get_wikitext(image_review['image_title'])
  article_wikitext = update_article_wikitext(article_wikitext, review_wikitext)
  api_client.set_wikitext(session_cookie, csrf_token, image_review['image_title'], article_wikitext)
