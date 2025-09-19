//Format a number representing a storage size to use binary prefixes
export function format_storage_units(value) {
  value = parseInt(value);

  //The value.toPrecision(4) function call below adds trailing zeroes to integer values, which can
  //make reading harder. Treat them specially here.
  if (value < 1024) {
    return value + ' B';
  }
  else {
    value /= 1024;  //The value is in KiB at least
  }

  //Perform the conversion to higher units, if needed
  const units = ['KiB', 'MiB', 'GiB', 'TiB'];
  let i = 0;

  for (i = 0; i < units.length - 1 && value >= 1024; i++) {
    value /= 1024;
  }

  return value.toPrecision(4) + ' ' + units[i];
}
