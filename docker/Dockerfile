FROM alpine:latest

#Install dependencies
RUN apk add python3

#Change to the installation directory
ARG APP_NAME="mw-unused-image-finder"
WORKDIR /$APP_NAME

#Setup the python virtual environment
ENV PYTHONUNBUFFERED=1
RUN --mount=source=setup-python.sh,target=setup-python.sh ./setup-python.sh
RUN python/bin/pip install gunicorn

#Make sure the mediawiki API URL is provided
ARG MEDIAWIKI_API
RUN if [ -z "$MEDIAWIKI_API" ]; then \
  echo "MEDIAWIKI_API build argument is missing";\
  exit 1;\
fi

#Also make sure that a CORS setting is provided
ARG CORS_PROXY
RUN if [ -z "$CORS_PROXY" ]; then \
  echo "CORS_PROXY build argument is missing";\
  exit 1;\
fi

#Create the configuration file
RUN cat <<EOF > config.toml
[mediawiki_server]
api = '$MEDIAWIKI_API'
cors_proxy = $CORS_PROXY

[sqlite3]
path = '/var/lib/$APP_NAME/db.sqlite3'
EOF

#Set up crond to run the update script at boot and then periodically
RUN mkdir /etc/periodic/5min/
RUN cat <<EOF >> /etc/crontabs/root
@reboot                                 /$APP_NAME/update_images.sh
*/5     *       *       *       *       /$APP_NAME/update_images.sh
EOF

#This wrapper script runs the image update script while preventing concurrent execution
RUN cat <<EOF > update_images.sh && chmod +x update_images.sh
cd /$APP_NAME
flock -x -n "/run/lock/update_images.lock" -c "python/bin/python -m update_images"
EOF

#This wrapper script runs all processes in the container
RUN cat <<EOF > /$APP_NAME/init.sh && chmod +x /$APP_NAME/init.sh
#Start cron in foreground mode, so the image update script log can be captured
crond -f &

#The gunicorn server will run at internal port 80
python/bin/gunicorn app:app -b 0.0.0.0:80 &

#Wait for any process to exit and return the status code of the process that exited first
wait -n
exit $?
EOF

#Install the server application files
COPY app.py update_images.py ./
COPY modules modules/
COPY templates templates/

#Set up a volume for the database and then initialize it
RUN mkdir /var/lib/$APP_NAME
VOLUME /var/lib/$APP_NAME
RUN --mount=source=initialize_db.py,target=initialize_db.py python/bin/python -m initialize_db

CMD ["./init.sh"]
