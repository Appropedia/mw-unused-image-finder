from collections.abc import Callable
import sqlite3
from flask import g
from modules.common import config

#Register module configurations
config.register({
  'sqlite3': {
    'path': 'db.sqlite3',
  },
})

#Create a new connection handle to the sqlite3 database
#Return value: The connection handle
def _new_conection() -> sqlite3.Connection:
  con = sqlite3.connect(config.root.sqlite3.path)
  con.execute('PRAGMA foreign_keys = 1')
  return con

#Obtain a connection handle to the sqlite3 database
#Return value: The connection handle
def get() -> sqlite3.Connection:
  #Attempt to retrieve the connection handle from the request context
  con = getattr(g, '_database', None)

  #Create and configure a new database connection if there isn't one yet
  if con is None:
    con = g._database = _new_conection()

  return con

#Close the potentially open connection handle to the sqlite3 database
def close() -> None:
  #Attempt to retrieve the connection handle from the request context
  con = getattr(g, '_database', None)

  #Proceed to close if needed
  if con is not None:
    con.close()

#Load a sqlite3 extension into the active connection if not loaded already
def load_extension(ext_name: str) -> None:
  #Attempt to retrieve the extension name list from the request context
  extensions = getattr(g, '_database_extensions', None)

  #Create a new extension name list if there isn't one yet
  if extensions is None:
    extensions = g._database_extensions = []

  #Load the extension if it's not in the list yet
  if ext_name not in extensions:
    con = get()
    con.enable_load_extension(True)
    con.load_extension(f'sqlite_extensions/{ext_name}.so')
    con.enable_load_extension(False)
    extensions.append(ext_name)

_schema_functions = []  #List of schema initialization functions

#Function decorator for registering schema initialization functions
def schema(func: Callable) -> Callable:
  _schema_functions.append(func)
  return func

#Call every schema initialization function to initialize the database
def initialize_schema() -> None:
  for init_func in _schema_functions:
    init_func()

#Reconfigure this module to operate outside of flask, preserving its API
def go_without_flask() -> None:
  global _con
  global get
  global close

  _con = _new_conection()       #Keep connection at module level, instead of application context
  get = lambda: _con            #Override get()
  close = lambda: _con.close()  #Override close()

#Open a direct connection to the database independently of any request context (the caller is
#responsible for calling the close method on the connnection once finished)
def contextless_get() -> sqlite3.Connection:
  return _new_conection()
