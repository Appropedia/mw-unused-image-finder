from modules.mediawiki_bot.wikitext_lexeme import lexeme_callback

#Dictionary for exported lexemes
magic_words = {}

#Text content from the review comments
@lexeme_callback(magic_words, 'REVIEWCOMMENTS')
def _reviewcomments(context: dict[str, int | str], *args):
  if len(args) > 0:
    return

  return context['comments']

#ISO 8601 review timestamp
@lexeme_callback(magic_words, 'REVIEWTIMESTAMP')
def _reviewtimestamp(context: dict[str, int | str], *args):
  if len(args) > 0:
    return

  return context['timestamp']

#Local account name of the review author
@lexeme_callback(magic_words, 'REVIEWAUTHOR')
def _reviewauthor(context: dict[str, int | str], *args):
  if len(args) > 0:
    return

  return context['author']
