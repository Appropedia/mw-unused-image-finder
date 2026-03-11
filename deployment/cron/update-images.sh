#Set a default python executable if not set
if [ -z "$PYTHON" ]; then
  PYTHON=python3
fi

#Change to the repository directory
cd $(dirname $0)/../..

#Run the image update script while preventing concurrent execution
flock -x -n "/tmp/update_images.lock" -c "$PYTHON -m update_images"
