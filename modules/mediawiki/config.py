from modules.common import config
from urllib.parse import urlparse

#Register module configurations
config.register({
  'mediawiki_server': {
    'api': str,
  }
})

#Perform initialization based on configuration
@config.on_load
def _on_load():
  #Parse and validate the API URL
  url = urlparse(config.root.mediawiki_server.api)
  if url.scheme not in ('http', 'https') or url.hostname is None or url.path == '':
    raise ValueError(f'Invalid URL for configuration mediawiki_server.api: '
                     f'{config.root.mediawiki_server.api}')

  #Append the parsed URL to the configuration
  config.root.mediawiki_server.url = url
