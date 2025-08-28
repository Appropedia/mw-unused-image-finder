import tomllib

#Nested-configuration handler class
#This provides storage and rule checking for configurations
class _nested_config:
  def __init__(self):
    #Start with an empty descriptor dictionary. This describes all available configurations and
    #their properties (read the register function for details).
    self._descriptors = {}

  #Define __setattr__ so that it only allows to add new attributes to the class and not modify them,
  #effectively making them immutable
  def __setattr__(self, name, value):
    if hasattr(self, name):
      raise AttributeError('Changing configurations in code is not allowed')

    super().__setattr__(name, value)

  #Register new configurations with the class
  #Parameters:
  # - descriptors: A dictionary describing the structure of the configuration, with keys defining
  #   configuration names and values defining configuration properties, according to their type:
  #   - Dictionary values describe nested configurations.
  #   - Type values (str, int, etc.) indicate the type of a required configuration.
  #   - Values of any other type indicate the default value and type of an optional configuration.
  # - path: A tuple containing the names of parent configurations, in descending order of hierarchy.
  def register(self, descriptors: dict, path: tuple = ()):
    for name, desc in descriptors.items():
      if isinstance(desc, dict):
        #If the provided descriptor is nested, check whether it's already registered
        if name not in self._descriptors:
          #If not registered, add it as an empty dictionary (so its type can be checked) and create
          #a nested object
          self._descriptors[name] = {}
          setattr(self, name, _nested_config())
        elif not isinstance(self._descriptors[name], dict):
          #If registered, make sure it was previously registered as nested
          raise ValueError(f'Configuration already registered: {'.'.join(path + (name,))}')

        #Register the nested descriptor with the nested object
        getattr(self, name).register(desc, path + (name,))

      else:
        #If the provided descriptor is not nested, simply add it exactly once
        if name not in self._descriptors:
          self._descriptors[name] = desc
        else:
          raise ValueError(f'Configuration already registered: {'.'.join(path + (name,))}')

  #Load a new set of configuration values
  #Parameters:
  # - initializers: A dictionary containing the values to load, with keys indicating the
  #   configuration names. Nested dictionaries indicate nested configuration initializers.
  # - path: A tuple containing the names of parent configurations, in descending order of hierarchy.
  def load(self, initializers: dict, warn_unknown: bool, path: tuple = ()):
    for name, value in initializers.items():
      #Make sure the provided initializer refers to a registered configuration (skip it otherwise)
      if name not in self._descriptors:
        if warn_unknown:
          print(f'Warning: Unknown configuration: {'.'.join(path + (name,))}')
        continue

      #If the associated descriptor is a type, then the expected type of the initializer is given
      #directly. Otherwise infer it from the type of the default value.
      expected_type = self._descriptors[name] if isinstance(self._descriptors[name], type) else \
                      type(self._descriptors[name])

      #Make sure the initializer if of the expected type.
      if not isinstance(value, expected_type):
        raise TypeError(f'Configuration value for {'.'.join(path + (name,))} '
                        f'must be {expected_type.__name__}')

      #Load the configuration initializer now. Recurse if nested.
      if isinstance(value, dict):
        getattr(self, name).load(value, warn_unknown, path + (name,))
      else:
        setattr(self, name, value)

  #Check for missing configurations and load defaults, if available
  #Parameters:
  # - path: A tuple containing the names of parent configurations, in descending order of hierarchy.
  def check_consistency(self, path: tuple = ()):
    for name, desc in self._descriptors.items():
      if isinstance(desc, dict):
        #If the descriptor is nested, recurse
        getattr(self, name).check_consistency(path + (name,))
      elif isinstance(desc, type):
        #If the descriptor is a type (required), make sure the configuration is loaded
        if not hasattr(self, name):
          raise RuntimeError(f'Missing required configuration: {'.'.join(path + (name,))}')
      else:
        #If the descriptor is of any other type (optional), load the default value if unavailable
        if not hasattr(self, name):
          setattr(self, name, desc)

#List of on_load event callbacks
_on_load_callbacks = []

#Function decorator for registering on_load event callbacks
def on_load(func):
  _on_load_callbacks.append(func)
  return func

#Root configuration instance
root = _nested_config()

#Register new configurations with the module
#Parameters:
# - descriptors: A dictionary describing the structure of the configuration. Check the register
#   method of the _nested_config class for details.
def register(descriptors: dict):
  root.register(descriptors)

#Load configurations from a .toml file
#Parameters:
# - toml_pathname: The pathname of the .toml file to load.
def load(toml_pathname: str, warn_unknown: bool = True):
  with open(toml_pathname, 'rb') as f:
    root.load(tomllib.load(f), warn_unknown)

  root.check_consistency()

  #Trigger the on_load event
  for callback in _on_load_callbacks:
    callback()
