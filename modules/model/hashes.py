from modules.model import db

#Schema initialization function
@db.schema
def init_schema():
  con = db.get()

  con.execute(
    f'CREATE TABLE IF NOT EXISTS hashes('
      f'revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE, '
      f'{', '.join(f'H{i} INT8' for i in range(8))})')

  for j in range(8):
    con.execute(
      f'CREATE INDEX IF NOT EXISTS hash_{j} ON hashes('
      f'{', '.join(f'H{i}' for i in range(j + 1))})')

#Create a new hash for a given image revision
def create(revision_id: int, hash_: tuple):
  con = db.get()
  con.execute(
    f'INSERT INTO hashes(revision_id, {', '.join(f'H{i}' for i in range(8))}) '
    f'VALUES ({', '.join('?' * 9)})',
    (revision_id,) + hash_)
  con.commit()

#Perform a recursive depth-first search on all image hashes in the table that are within a maximum
#hamming distance from a given reference hash
#Parameters:
# - ref_hash: The hash that is used as a reference point for the search.
# - max_dist: The maximum allowed hamming distance. Image hashes farther than this are excluded.
# - cand_hash: For recursive calls only - The current candidate hash. A partial hash that is within
#              the maximum hamming distance and is currently being analyzed.
# - cand_dist: For recursive calls only - The hamming distance of the current candidate hash.
#Return value: A set with the revision ids of the images of which the hash is within the maximum
#              hamming distance.
def search(ref_hash: tuple, max_dist: int, cand_hash: tuple = (), cand_dist: int = 0) -> set[int]:
  con = db.get()

  #The hash level represents the current depth of the search. It counts the amount of bytes of the
  #current candidate hash.
  hash_level = len(cand_hash)

  #Search for all distinct hahses in the current hash level, using the candidate hash as the fixed
  #portion for all previous levels
  hash_byte_cursor = con.cursor()
  hash_byte_cursor.execute(
    f'SELECT DISTINCT H{hash_level} FROM hashes WHERE H{hash_level} IS NOT NULL'
    f'{''.join(f' AND H{i}=?' for i in range(hash_level))}',
    cand_hash)
  hash_byte_cursor.row_factory = lambda cur, row: row[0]

  matches = set()
  for hash_byte in hash_byte_cursor:
    #Find all bits that differ from the reference hash at the same level by using an XOR mask, then
    #count the bits that are set and add them to the new candidate distance
    different_bits = hash_byte ^ ref_hash[hash_level]
    new_cand_dist = cand_dist
    while different_bits > 0:
      different_bits &= different_bits - 1
      new_cand_dist += 1

    #Exclude hashes with a hamming distance that exceeds the maximum allowed
    if new_cand_dist > max_dist:
      continue

    #The hamming distance is adequate. Append this byte to the new candidate hash.
    new_cand_hash = cand_hash + (hash_byte,)

    if hash_level < 7:
      #Maximum hash level not reached - recurse
      matches.update(search(ref_hash, max_dist, new_cand_hash, new_cand_dist))
    else:
      #Maximum hash level reached (hash is complete). Search for all hashes matching the candidate
      #hash and add the corresponding revision ids to the matches.
      rev_id_cursor = con.cursor()
      rev_id_cursor.execute(
        f'SELECT revision_id FROM hashes WHERE {' AND '.join(f'H{i}=?' for i in range(8))}',
        new_cand_hash)
      rev_id_cursor.row_factory = lambda cur, row: row[0]
      matches.update(rev_id_cursor.fetchall())

  return matches
