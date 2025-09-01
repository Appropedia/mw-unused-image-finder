from collections.abc import Iterator
from urllib3 import HTTPConnectionPool, HTTPSConnectionPool
from modules.common import config
from modules.mediawiki import config as mw_config

#Perform initialization based on configuration
@config.on_load
def _on_load():
  global _pool

  #Create a connection pool based on the connection scheme
  server = config.root.mediawiki_server.url
  _pool = HTTPConnectionPool(server.hostname, server.port) if server.scheme == 'http' else\
          HTTPSConnectionPool(server.hostname, server.port)

#Create a generator object that performs continued queries to a mediawiki server
#Parameters:
# - params: A dictionary containing query parameters
#Return value: A generator object that returns dictionaries with response data
def query(params: dict) -> Iterator[dict]:
  params['format'] = 'json'   #Make sure to request json format

  while True:
    #Perform the request and get the response
    server = config.root.mediawiki_server.url
    rsp = _pool.urlopen(
      'GET',
      server.path + '?' + '&'.join(f'{key}={val}' for key, val in params.items()))

    #Make sure the response is 200 - OK
    if rsp.status != 200:
      raise ConnectionError(f'Error code {rsp.status} - {rsp.reason}')

    #Read the response data, parse the JSON and yield it
    rsp_data = rsp.json()
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
