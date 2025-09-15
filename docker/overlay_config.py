from argparse import ArgumentParser
import sys, io
import tomllib

#Overlay a nested dictionary onto another, adding or overriding values.
#Parameters:
# - taget: The nested dictionary where data is put.
# - overlay: The nested dictionary from where data is taken.
def overlay(target_dict: dict, overlay_dict: dict):
  #Iterate the overlay dictionary
  for o_key, o_val in overlay_dict.items():
    if o_key not in target_dict:
      #The entry doesn't exist, simply add the new entry. If it's a dictionary it'll bring in
      #everyhing (no need to recurse).
      target_dict[o_key] = o_val
    else:
      #The entry exists
      if isinstance(target_dict[o_key], dict) and isinstance(o_val, dict):
        #Both the target and overlay entries are dictionaries, recurse
        overlay(target_dict[o_key], o_val)
      else:
        #One or none of the entries are dictionaries:
        # - If only the target entry is a dictionary, it'll get its contents replaced entirely by a
        #   single item.
        # - If only the overlay entry is a dictionary, it'll bring in everyhing and replace the
        #   single item (no need to recurse).
        # - If none is a dictionary the item will simply be replaced.
        target_dict[o_key] = o_val

#Create a generator expression that returns all non dictionary (nested) items in a dictionary.
def non_dict_items(d: dict):
  return ((key, val) for key, val in d.items() if not isinstance(val, dict))

#Create a generator expression that returns all dictionary (nested) items in a dictionary.
def dict_items(d: dict):
  return ((key, val) for key, val in d.items() if isinstance(val, dict))

#Serialize a dictionary containing TOML data as text.
#Parameters:
# - d: The dictionary with TOML data.
# - f: A text file descriptor to write data to.
# - path: For recursion purposes only - the current path in the TOML structure.
def generate_toml(d: dict, f: io.TextIOWrapper, path: tuple = ()):
  header = True
  for key, val in non_dict_items(d):
    #Print the table header once only if the path isn't empty (e.g.: "root")
    if header and path:
      print(f'[{'.'.join(path)}]', file = f)
      header = False

    #Print the values according to their type
    match val:
      case bool():
        print(f'{key} = {'true' if val else 'false'}', file = f)
      case int():
        print(f'{key} = {val}', file = f)
      case str():
        print(f'{key} = "{val}"', file = f)
      case _:
        raise ValueError(f'Unsupported type: {type(val)}')

  #Print an extra line if a table was printed
  if not header: print(file = f)

  #Recurse for nested dictionaries
  for key, val in dict_items(d):
    generate_toml(val, f, path + (key,))

#Register the program arguments
parser = ArgumentParser(description = 'Overlay a TOML configuration file onto another, adding or '
                                      'overriding configurations',
                        epilog = 'Note: This is NOT a general TOML manipulation tool, it\'s '
                                 'intended for use only in the context of this project. It '
                                 'performs destructive operations on the target file, so use with '
                                 'caution.')
parser.add_argument('target_toml',
                    help = 'The TOML which will receive overlay configurations')
parser.add_argument('overlay_toml',
                    help = 'The TOML file that provides the overlay configurations. If set to '
                           '"-", read from stdin.')
args = parser.parse_args()

#Load the target TOML file
with open(args.target_toml, 'rb') as f:
  target_dict = tomllib.load(f)

#Load the overlay TOML from stdin if specified, otherwise load from a file
if args.overlay_toml == '-':
  overlay_dict = tomllib.load(sys.stdin.buffer)
else:
  with open(args.overlay_toml, 'rb') as f:
    overlay_dict = tomllib.load(f)

#Apply the overlay
overlay(target_dict, overlay_dict)

#Write to the target TOML file
with open(args.target_toml, 'w') as f:
  generate_toml(target_dict, f)
