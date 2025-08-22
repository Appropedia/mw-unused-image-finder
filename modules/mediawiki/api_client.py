from urllib.parse import urlparse
import http.client
import json
from modules.common import config

config.register({
  'mediawiki_server': {
    'api': str,
  }
})

_conn = None

#Close the client connection
def close():
  _conn.close()

#Create a generator object that performs continued queries to a mediawiki server
#Parameters:
# - params: A dictionary containing query parameters
#Return value: The generator object
def query(params: dict):
  global _server
  global _conn

  #Create a new connection once (delayed due to the timing of configuration loading)
  if _conn is None:
    #Parse and validate the API URL
    _server = urlparse(config.root.mediawiki_server.api)
    if _server.scheme not in ('http', 'https') or _server.hostname is None or _server.path == '':
      raise ValueError(f'Invalid URL for configuration mediawiki_server.api: '
                       f'{config.root.mediawiki_server.api}')

    _conn = http.client.HTTPConnection(_server.hostname) if _server.scheme == 'http' else\
            http.client.HTTPSConnection(_server.hostname)

  params['format'] = 'json'   #Make sure to request json format

  while True:
    #Perform the request and get the response
    _conn.request('GET',
                  _server.path + '?' + '&'.join(f'{key}={val}' for key, val in params.items()))
    rsp = _conn.getresponse()

    #Make sure the response is 200 - OK
    if rsp.status != 200:
      raise ConnectionError(f'Error code {rsp.status} - {rsp.reason}')

    #Read the response data, parse the JSON and yield it
    rsp_data = json.loads(rsp.read())
    yield rsp_data

    #Check whether there's a continue parameter in the structure
    if 'continue' in rsp_data and 'continue' in rsp_data['continue']:
      #Parse the continue parameter
      continue_tokens = rsp_data['continue']['continue'].split('||')
      if len(continue_tokens) == 2 and continue_tokens[0] != '-' and continue_tokens[1] == '':
        #Parsing successful
        continue_param = continue_tokens[0]

        #Add the continue parameter value to the request, if present
        if continue_param in rsp_data['continue']:
          params[continue_param] = rsp_data['continue'][continue_param]
          continue

    break   #No continuation, parsing failed or continue response not structured as expected
