from urllib.parse import urlencode
from urllib3 import HTTPConnectionPool, HTTPSConnectionPool
from modules.common import config
from modules.mediawiki import config as mw_config

#Note: The cookie model implemented here is extremely simplistic. The 'Set-Cookie' header is simply
#translated from the server response to the 'Cookie' header in the next request. This model is
#enough for current bot functionality but might need to be expanded to use something like
#http.cookiejar in case of adding more features in the future.

#Perform initialization based on configuration
@config.on_load
def _on_load():
  global _pool

  #Create a connection pool based on the connection scheme
  server = config.root.mediawiki_server.url
  _pool = HTTPConnectionPool(server.hostname, server.port) if server.scheme == 'http' else\
          HTTPSConnectionPool(server.hostname, server.port)

#Perform a server query and get parsed JSON data and cookies
#Parameters:
# - method: The HTTP method ('GET' or 'POST')
# - params: A dictionary with the query params, which are encoded in the request URL for GET
#           requests or the request body for 'POST' reqquests.
# - cookies: An optional string with the current session cookies.
#Return value: A tuple consisting og the parsed JSON data as a dictionary and the cookies returned
#by the server as a string or None in case no cookies are returned.
def _query(method: str, params: dict[str, str],
           cookies: str | None = None) -> tuple[dict[str, any], str | None]:
  params['format'] = 'json'   #Make sure to request json format

  match method:
    case 'GET':
      #Request parameters go in the url for GET requests
      server_url = f'{config.root.mediawiki_server.url.path}?{urlencode(params)}'
      body = None
      headers = {}
    case 'POST':
      #Request parameters go in the body for POST requests
      server_url = config.root.mediawiki_server.url.path
      body = urlencode(params)
      headers = { 'Content-Type': 'application/x-www-form-urlencoded' }
    case _:
      raise ValueError('Invalid HTTP method')

  if cookies is not None:
    headers['Cookie'] = cookies

  #Perform the request now
  rsp = _pool.urlopen(method, server_url, body, headers)

  #Make sure the response is 200 - OK
  if rsp.status != 200:
    raise ConnectionError(f'Error code {rsp.status} - {rsp.reason}')

  #Return the parsed JSON data and the cookies if present
  return rsp.json(), rsp.headers['Set-Cookie'] if 'Set-Cookie' in rsp.headers else None

#Log in with the given username and password and return the corresponding session cookie and a csrf
#token for editing
def login(username: str, password: str) -> tuple[str, str]:
  #Perform the first request for a login token and get the response
  rsp_data, session_cookie = _query('GET', { 'action': 'query', 'meta': 'tokens', 'type': 'login' })

  #Make sure the login token is present in the response, then get its contents
  if 'query' not in rsp_data or 'tokens' not in rsp_data['query'] or \
     'logintoken' not in rsp_data['query']['tokens']:
    raise ValueError('Unexpected server response: Login token not present')

  login_token = rsp_data['query']['tokens']['logintoken']

  #Also make sure cookies are present in the response
  if session_cookie is None:
    raise ValueError('Unexpected server response: Session cookie not present')

  #Perform the second request for actual login and get the response
  rsp_data, session_cookie = _query('POST',
                                    { 'action': 'login', 'lgname': username, 'lgpassword': password,
                                      'lgtoken': login_token },
                                    session_cookie)

  #Make sure the result is successful
  if 'login' not in rsp_data or 'result' not in rsp_data['login']:
    raise ValueError('Unexpected server response: Login result not present')

  if rsp_data['login']['result'] != 'Success':
    raise ValueError('Unexpected server response: Login not successful')

  #Make sure cookies are also present in the response
  if session_cookie is None:
    raise ValueError('Unexpected server response: Session cookie not present')

  #Get a CSRF token for editing
  rsp_data, _ = _query('GET',
                       { 'action': 'query', 'meta': 'tokens', 'type': 'csrf' },
                       session_cookie)

  #Make sure the CSRF token is present in the response, then get its contents
  if 'query' not in rsp_data or 'tokens' not in rsp_data['query'] or \
     'csrftoken' not in rsp_data['query']['tokens']:
    raise ValueError('Unexpected server response: CSRF token not present')

  csrf_token = rsp_data['query']['tokens']['csrftoken']

  return session_cookie, csrf_token

#Retrieve the contents of a given page
def get_wikitext(title: str) -> str:
  rsp_data, _ =  _query('GET',
                        { 'action': 'query', 'prop': 'revisions', 'titles': title,
                          'rvprop': 'content', 'rvslots': 'main' })

  #Make sure there's page information in the response
  if 'query' not in rsp_data or 'pages' not in rsp_data['query'] or \
     len(rsp_data['query']['pages']) == 0:
    raise ValueError('Unexpected server response: No pages returned')

  #Since the search is for a single page title, get the first (and only) page id, then get the
  #corresponding data
  page_id = next(iter(rsp_data['query']['pages']))
  page_data = rsp_data['query']['pages'][page_id]

  #Make sure there is at least one revision defined for the page, then get that revision
  if 'revisions' not in page_data or len(page_data['revisions']) == 0:
    raise ValueError('Unexpected server response: The page has no revisions')

  revision_data = page_data['revisions'][0]

  #Make sure there's a main slot, then get its contents
  if 'slots' not in revision_data or 'main' not in revision_data['slots']:
    raise ValueError('Unexpected server response: The page has no main revision slot')

  main_slot = revision_data['slots']['main']

  #Make sure the content format is wiki text
  if 'contentmodel' not in main_slot or main_slot['contentmodel'] != 'wikitext' or \
     'contentformat' not in main_slot or main_slot['contentformat'] != 'text/x-wiki':
    raise ValueError('Unexpected server response: Unexpected content format')

  #Make sure there's a content field and return it
  if '*' not in main_slot:
    raise ValueError('Unexpected server response: Response lacks content')

  return main_slot['*']

#Update the contents of a given page
def set_wikitext(session_cookie: str, csrf_token: str, title: str, content: str) -> None:
  rsp_data, _ = _query('POST',
                       { 'action': 'edit', 'title': title, 'text': content, 'token': csrf_token },
                       session_cookie)

  if 'edit' not in rsp_data or 'result' not in rsp_data['edit']:
    raise ValueError('Unexpected server response: Edit result not present')

  return rsp_data['edit']['result'] == 'Success'
