from collections.abc import Callable

#Type hint for stored handlers
Callback = Callable[..., str]

#Function decorator for registering handlers of lexemes (magic words or parser functions)
#Parameters:
# - handlers: A dictionary where the decorated callback will be stored
# - name: The name of the lexeme
def lexeme_callback(handlers: dict[str, Callback], name: str) -> Callable[[Callback], Callback]:
  def wrapper(func: Callback) -> Callback:
    if name in handlers:
      raise ValueError(f'Duplicate callback function: {name}')

    handlers[name] = func
    return func

  return wrapper
