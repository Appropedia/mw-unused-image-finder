#include <sqlite3ext.h>
SQLITE_EXTENSION_INIT1

//Calculate the hamming distance between two 64-bit numbers. This implementation is intentionally
//small with the intention to be fast and is aimed at numbers stored in the native 64-bit format.
//The calculation works by obtaining the bits that are different using an XOR mask and then counting
//the bits that are set using one of the GCC's built-in "popcount" (population count) functions.
//The intrinsic uses the POPCNT instruction of the x86 processors, which is inherently fast.
void hammdist(sqlite3_context *context, int argc, sqlite3_value **argv) {
  sqlite3_int64 a = sqlite3_value_int64(argv[0]);
  sqlite3_int64 b = sqlite3_value_int64(argv[1]);
  sqlite3_result_int64(context, __builtin_popcountll(a ^ b));
}

//Initialize this plugin and register the functions defined here
int sqlite3_hammdist_init(sqlite3 *db, char **pzErrMsg, const sqlite3_api_routines *pApi) {
  SQLITE_EXTENSION_INIT2(pApi);
  return sqlite3_create_function(db, "hammdist", 2, SQLITE_UTF8, 0, hammdist, 0, 0);
}
