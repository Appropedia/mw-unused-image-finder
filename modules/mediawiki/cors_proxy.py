#+-------------------------------------------------------------------------------------------------+
#| The Cross Origin Resource Sharing (CORS) proxy functionality allows to handle all frontend      |
#| requests to the mediawiki server API through the current Flask server instance.                 |
#|                                                                                                 |
#| In theory this should be safe, as trust is given to the mediawiki server anyway, but it's       |
#| disabled by default so the user has to willingly take the action to turn it on if needed.       |
#|                                                                                                 |
#| When disabled the main application only sees an empty blueprint, so the endpoint is not         |
#| registered. Also, the user must make sure that the mediawiki server lists the current Flask     |
#| server instance as allowed to make cross requests, by including it in the HTTP header called    |
#| "Access-Control-Allow-Origin"; otherwise browsers might fail to make API requests.              |
#+-------------------------------------------------------------------------------------------------+

from flask import Blueprint, url_for, request, make_response
from urllib.parse import urlencode
from urllib3 import HTTPConnectionPool, HTTPSConnectionPool
from modules.common import config
from modules.mediawiki import config as mw_config

#Register module configurations
config.register({
  'mediawiki_server': {
    'cors_proxy': False,
  },
})

#Flask blueprint instance
blueprint = Blueprint('cors_proxy', __name__, url_prefix = '/cors_proxy')

#Perform initialization based on configuration
@config.on_load
def _on_load():
  if config.root.mediawiki_server.cors_proxy:
    #CORS proxy is enabled. Create a connection pool based on the connection scheme.
    global _pool
    server = config.root.mediawiki_server.url
    _pool = HTTPConnectionPool(server.hostname, server.port) if server.scheme == 'http' else\
            HTTPSConnectionPool(server.hostname, server.port)

    #Add the route handler and set the frontend API configuration to that
    blueprint.route('/api')(api)
    config.root.mediawiki_server.frontend_api = lambda: url_for('cors_proxy.api')
  else:
    #CORS proxy disabled. Set the frontend API to the mediawiki server.
    config.root.mediawiki_server.frontend_api = lambda: config.root.mediawiki_server.api

#When enabled this function handles @blueprint.route('/api')
def api():
  #Make the request to the mediawiki server on behalf of the client and relay the query parameters
  server = config.root.mediawiki_server.url
  mw_resp = _pool.urlopen('GET', f'{server.path}?{urlencode(request.args)}')

  #Create a response for the client and relay the response data and status code
  resp = make_response(mw_resp.data)
  resp.status = mw_resp.status
  return resp
