import enum
from typing import Iterator
import subprocess, threading, queue, sys
import PIL, io, imagehash
from modules.common import config

#Register module configurations
config.register({
  'perceptual_hashing': {
    'resolution_limit': 10000000,   #Default: 10 Mega pixel
    'image_magick_max_mem': '',     #Default: No memory limit (example: '256MiB')
  }
})

#Error codes for module functions
class status(enum.Enum):
  OK          = enum.auto()
  OUT_OF_MEM  = enum.auto()
  UNSUPPORTED = enum.auto()

#Thread function used for receiving data from a subprocess.
#Parameters:
# - pipe: The output pipe (stdout, stderr).
# - queue: The queue used to send output data.
def input_thread(pipe: io.BufferedReader, queue: queue.Queue):
  while True:
    #Attempt to read the pipe. This operation blocks while waiting for more data. The process will
    #close it once it finishes, in which case an empty bytes object is returned.
    data = pipe.read()
    if data:
      queue.put(data)
    else:
      pipe.close()
      break

#Pillow is pretty bad at managing large images in memory, causing large memory usage spikes. This
#function invokes ImageMagick to check the size of an image and scale it down to a manageable size,
#if needed. By not scaling images in python, the memory allocated to the process stays in check, as
#python doesn't always give the memory back to the system.
#Parameters:
# - stream: An iterator object that is used to provide the raw image data to ImageMagick.
#Return value: A tuple with 3 elements:
# - The status of the operation.
# - The total amount of data retrieved from the stream. This is always returned, even in case of
#   error.
# - A bytes object containing either the reduced image or the original. Or None in the case of
#   ImageMagick returning an error (e.g.: the file is not an image).
def resize_image_if_needed(stream: Iterator[bytes]) -> tuple[status, int, bytes | None]:
  #Prepare the program arguments
  max_mem = config.root.perceptual_hashing.image_magick_max_mem
  res_lim = config.root.perceptual_hashing.resolution_limit
  args  = ['magick']
  args += ['-limit', 'memory', max_mem] if max_mem else []
  args += ['-', '-thumbnail', f'{res_lim}@>', '-']

  #Start the program
  process = subprocess.Popen(args, stdin = subprocess.PIPE, stdout = subprocess.PIPE)

  #Prepare a queue for receiving the resulting image data, then create and start the thread for
  #reception
  stdout_queue = queue.Queue()

  stdout_thread = threading.Thread(target = input_thread,
                                   args = (process.stdout, stdout_queue),
                                   daemon = True)

  stdout_thread.start()

  #Feed the program with the data stream while counting the data, then close the stdin stream to
  #signal that the data is over
  input_file_size = 0
  for chunk in stream:
    process.stdin.write(chunk)
    input_file_size += len(chunk)

  process.stdin.close()

  #Wait for the data to be received completely by waiting on the related thread, then wait for the
  #program to finish
  stdout_thread.join()
  process.wait()

  if process.returncode != 0:
    #Something went wrong (the file is possibly not a supported image)
    print(f'ImageMagick returned with error code {process.returncode}', file = sys.stderr)
    if process.returncode == -9:
      return (status.OUT_OF_MEM, input_file_size, None)
    else:
      return (status.UNSUPPORTED, input_file_size, None)

  #Assemble the data into a single bytes object
  stdout_data = b''
  while not stdout_queue.empty():
    stdout_data += stdout_queue.get()

  return (status.OK, input_file_size, stdout_data)

#Calculate up to four hashes (one for every 90 degree rotation) for a given image.
#Parameters:
# - stream: An iterator object that is used to provide the raw image data for hashing.
#Return value: A tuple with 3 elements:
# - The status of the operation.
# - The total amount of data retrieved from the stream. This is always returned, even in case of
#   error.
# - A set of tuples, with each tuple containing a hash, or None in case of error.
def calculate_phashes(stream: Iterator[bytes]) -> tuple[status, int, set[tuple] | None]:
  #Resize the image with ImageMagick, if needed
  s, input_file_size, raw_data = resize_image_if_needed(stream)

  if s != status.OK:
    return (s, input_file_size, None)

  #Open the raw data from the potentially resized image with PIL
  try:
    img = PIL.Image.open(io.BytesIO(raw_data))
  except PIL.UnidentifiedImageError:
    #The image file could not be recognized
    return (status.UNSUPPORTED, input_file_size, None)

  #Calculate the hash for every 90 degreee rotation of this image, structuring each as individual
  #bytes in a tuple
  hashes = set()  #Use a set to reduce the hashes of images with rotational symmetry
  for angle in range(0, 360, 90):
    string_hash = str(imagehash.phash(img.rotate(angle, expand = True)))
    tuple_hash = tuple(int(string_hash[i: i+2], 16) for i in range(0, len(string_hash), 2))
    hashes.update(set((tuple_hash,)))

  return (status.OK, input_file_size, hashes)
