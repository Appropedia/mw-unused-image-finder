from modules.common import config

#Register configurations for the flask application module
config.register({
  'security': {
    'flask_secret_key_file': 'flask_secret_key.bin',
  },
  'reverse_proxy': {
    'enabled': False,
  },
})
