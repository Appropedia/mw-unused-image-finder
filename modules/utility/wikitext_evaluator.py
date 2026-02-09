from collections.abc import Iterator
from typing import Self

RECURSION_LIMIT = 32

#Lexical analyzer implementation
class _LexicalAnalyzer:
  def __init__(self, wikitext: str) -> None:
    self.wikitext = wikitext
    self.pos = 0

  #Count the amount of successive characters from the current position
  def _count_successive_chars(self) -> int:
    reference_char = self.wikitext[self.pos]
    count = 0

    #Keep counting until a different character is found or the wikitext ends
    for char in self.wikitext[self.pos:]:
      if char == reference_char:
        count += 1
      else:
        break

    return count

  #Tokenize the wikitext by splitting it into segments that contain regular text and segments that
  #contain consecutive braces. Return an empty string when the input ends.
  def next_token(self) -> str:
    start_pos = self.pos

    #Traverse the input wikitext until a set of consecutive braces is found or the current set ends
    for self.pos in range(self.pos, len(self.wikitext)):
      match self.wikitext[self.pos]:
        case '|':
          #A pipe was found, check the current position
          if self.pos == start_pos:
            #If the pipe is at the starting position advance the current position by 1 so it's
            #returned alone, otherwise return all characters from starting position to exclude it
            self.pos += 1

          return self.wikitext[start_pos:self.pos]
        case '{' | '}':
          #A brace was found, check how many are there in the set
          brace_count = self._count_successive_chars()

          #If the set doesn't contain at least 2 braces ignore it and keep traversing, otherwise
          #return a token
          if brace_count >= 2:
            #If the set is at the starting position advance the current position by the amount of
            #braces so they are returned together. If the set is not at the starting position then
            #return all characters from starting position, excluding the set.
            if self.pos == start_pos:
              self.pos += brace_count

            return self.wikitext[start_pos:self.pos]

    #The loop ended and no set of consecutive braces was found. Set the position to the end and
    #return all characters from starting position.
    self.pos = len(self.wikitext)
    return self.wikitext[start_pos:]

#Abstract syntax tree representation. This is just a wrapper over a list that performs smart string
#concatenation.
class _AST:
  def __init__(self, data = ()) -> None:
    self._data = [*data]

  def __iter__(self) -> Iterator[str | dict]:
    return self._data.__iter__()

  #Check whether smart string concatenation should be performed
  def _should_concatenate(self, index: int, new_item: str | dict) -> bool:
    #Conditions:
    # - The list must be populated
    # - The element at the provided index and the new element must be strings
    # - The element at the provided index and the new element must not be pipes
    #Note: There's an additional requirement that the index must point to either the start or the
    #end of the list, but this is enforced by hard coding the index parameter to either 0 or -1
    return len(self._data) > 0 and isinstance(self._data[index], str) and \
           isinstance(new_item, str) and self._data[index] != '|' and new_item != '|'

  #Prepend a single element by performing smart string concatenation
  def prepend(self, item: str | dict) -> None:
    if self._should_concatenate(0, item):
      self._data[0] = item + self._data[0]
    else:
      self._data.insert(0, item)

  #Append a single element by performing smart string concatenation
  def append(self, item: str | dict) -> None:
    if self._should_concatenate(-1, item):
      self._data[-1] += item
    else:
      self._data.append(item)

  #Extend this AST with another AST
  def extend(self, ast: Self) -> None:
    for item in ast._data:
      self.append(item)

  #Retrieve and remove the last item
  def pop(self) -> str | dict:
    return self._data.pop()

  #Retrieve the last item
  def last(self) -> str | dict:
    return self._data[-1]

#Parser implementation
class _Parser:
  def __init__(self, wikitext: str) -> None:
    self.lexer = _LexicalAnalyzer(wikitext)

  #Perform the gobal parsing process
  def parse(self) -> _AST:
    ast = _AST()

    #Consume tokens until end of input
    while token := self.lexer.next_token():
      if _is_repeated_sequence(token, '{'):
        #Brace block start found, parse the block
        ast.extend(self._parse_block(token))
      else:
        #The token is either plain text or right braces, treat both as plain text
        ast.append(token)

    return ast

  #Perform recursive parsing of brace blocks
  def _parse_block(self, l_braces: str) -> _AST:
    result = _AST()

    #Consume tokens until no more pending left braces or end of input
    while len(l_braces) >= 2 and (token := self.lexer.next_token()):
      match token:
        case '|':
          result.append(token)
        case _ if _is_repeated_sequence(token, '{'):
          #Brace block start found, recurse
          result.extend(self._parse_block(token))

          if _is_repeated_sequence(result.last(), '}'):
            #Leftover right braces found, take them and attempt to nest with the pending left braces
            r_braces = result.pop()
            l_braces, result, r_braces = _nest(l_braces, result, r_braces)

            if r_braces:
              #Leftover right braces remain after nesting, return them to the caller by appending
              result.append(r_braces)
        case _ if _is_repeated_sequence(token, '}'):
          #Brace block end found, attempt to nest with the pending left braces
          l_braces, result, r_braces = _nest(l_braces, result, token)

          if r_braces:
            #Leftover right braces remain after nesting, return them to the caller by appending
            result.append(r_braces)
        case _:
          #Append any other token not related to brace blocks
          result.append(token)

    if l_braces:
      #Only 1 pending left brace or end of input reached with leftover left braces, prepend the
      #braces to the result
      result.prepend(l_braces)

    return result

#Check whether the string is a repeated sequence of at least 2 characters
def _is_repeated_sequence(string: str, character: str) -> bool:
  return len(string) >= 2 and string == character * len(string)

#Given any amount of left and right braces and AST content, attempt to nest the AST content as much
#as possible by using intermediate dictionaries, taking as many braces as possible in each level. If
#nesting is not possible return the same parameters that were given, otherwise return the remaining
#braces (if any) and the nested AST content.
def _nest(l_braces: str, content: _AST, r_braces: str) -> tuple[str, _AST, str]:
  while (brace_count := min(len(l_braces), len(r_braces), 3)) >= 2:
    content = _AST([{
      'l_braces': '{' * brace_count,
      'content': content,
      'r_braces': '}' * brace_count,
    }])
    l_braces = l_braces[:-brace_count]
    r_braces = r_braces[:-brace_count]

  return l_braces, content, r_braces

#Perform recursive evaluation of brace blocks
def _evaluate_block(block: dict[str, str | _AST], lexicon: dict[str, any],
                    recursion_count: int) -> str:
  #Create a new arguments list by concatenating brace block contents while keeping pipes separate
  args = ['']
  for item in block['content']:
    match item:
      case '|':
        #Expand pipe tokens into pipes and empty strings so that if evaluation analysis fails, the
        #current brace block can be returned without any modification other than recursive expansion
        args.append('|')
        args.append('')
      case dict():
        #If a nested brace block is found evaluate it recursively first so it becomes a string that
        #can be concatenated
        args[-1] += _evaluate_block(item, lexicon, recursion_count)
      case _:
        #Concatenate any other string unconditionally
        args[-1] += item

  #Start evaluation analysis by trimming spaces before the first item in the argument list, which
  #may be a magic word or a parser function name
  head = args[0].lstrip()

  #If the head starts with a hash and can be split with the first occurrence of a colon it's a
  #parser function call
  if head.startswith('#') and len(pair := head.split(':', 1)) == 2:
    #Split the function name and the first argument, but discard the hash
    function_name = pair[0][1:]
    first_arg = pair[1]

    #Call the parser function if registered
    if 'parser_functions' in lexicon and function_name in lexicon['parser_functions']:
      #The argument list contains pipes in its odd positions so make sure to omit them
      handler = lexicon['parser_functions'][function_name]
      result = handler(lexicon.get('context'), *[first_arg] + args[2::2])
      if result is not None:
        #Parse and evaluate the new result recursively
        result = evaluate(result, lexicon, recursion_count + 1)
        return result

  #Continue evaluation analysis by completely stripping the head and checking if it's a registered
  #magic word
  head = head.rstrip()
  if 'magic_words' in lexicon and head in lexicon['magic_words']:
    #Call the magic word handler by omitting arguments in odd positions as well
    handler = lexicon['magic_words'][head]
    result = handler(lexicon.get('context'), *args[2::2])
    if result is not None:
      #Parse and evaluate the new result recursively
      result = evaluate(result, lexicon, recursion_count + 1)
      return result

  #If flow reaches this point the evaluation analysis or the evaluation itself failed so return the
  #brace block as text by concatenating every element in it
  return block['l_braces'] + ''.join(args) + block['r_braces']

#Perform parsing and evaluation of a given piece of wikitext using a given lexicon
#Parameters:
# - wikitext: The wikitext string to be evaluated
# - lexicon: A dictionary with the following keys:
#   - 'magic_words': A dictionary with magic word names as keys and callable handlers as data
#   - 'parser_functions': A similar dictionary with parser function names and callable handlers
#                         (names must omit the initial hash)
#   - 'context': An object of any type containing information relevant to the evaluation of both
#                magic words and parser functions
# - _recursion_count: Internal use only - used to enforce recursion limit
#   Note: all keys are optional
def evaluate(wikitext: str, lexicon: dict[str, any], _recursion_count: int = 0) -> str:
  if _recursion_count > RECURSION_LIMIT:
    return 'Recursion limit reached'

  #Instantiate the parser and proceed to parse
  parser = _Parser(wikitext)
  ast = parser.parse()

  #Evaluate the wikitext by iterating through the AST
  result = ''
  for item in ast:
    if isinstance(item, dict):
      #Brace block found, evaluate it recursively
      result += _evaluate_block(item, lexicon, _recursion_count)
    else:
      #Any other token outside of any brace block is simply concatenated with the result
      result += item

  return result
