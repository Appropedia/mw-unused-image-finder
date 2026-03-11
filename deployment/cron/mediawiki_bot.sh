#Set a default python executable if not set
if [ -z "$PYTHON" ]; then
  PYTHON=python3
fi

#Change to the repository directory
cd $(dirname $0)/../..

#Run the mediawiki bot script while preventing concurrent execution
flock -x -n "/tmp/mediawiki_bot.lock" -c "$PYTHON -m mediawiki_bot"
