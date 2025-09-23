FROM alpine:latest

#Install dependencies
RUN apk add python3
RUN apk add imagemagick
RUN apk add libjpeg-turbo

#Change to the installation directory
ARG APP_NAME="mw-unused-image-finder"
WORKDIR /$APP_NAME

#Setup the python virtual environment
ARG SRC_DIR
ENV PYTHONUNBUFFERED=1
RUN --mount=source=$SRC_DIR/setup-python.sh,target=setup-python.sh ./setup-python.sh
RUN python/bin/pip install gunicorn

#Make sure the configuration file is provided
ARG CONFIG_FILE
RUN if [ -z "$CONFIG_FILE" ]; then \
  echo "CONFIG_FILE build argument is missing";\
  exit 1;\
fi

#Copy the provided configuration file, then overlay the database path configuration
COPY $CONFIG_FILE config.toml
RUN --mount=source=$SRC_DIR/docker/overlay_config.py,target=overlay_config.py\
    python/bin/python -m overlay_config config.toml - <<EOF
[sqlite3]
path = '/var/lib/$APP_NAME/db.sqlite3'

[security]
flask_secret_key_file = '/var/lib/$APP_NAME/flask_secret_key.bin'
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
COPY $SRC_DIR/app.py $SRC_DIR/update_images.py ./
COPY $SRC_DIR/modules modules/
COPY $SRC_DIR/templates templates/
COPY $SRC_DIR/assets assets/

#Set up a volume for the database and then initialize it
RUN mkdir /var/lib/$APP_NAME
VOLUME /var/lib/$APP_NAME
RUN --mount=source=$SRC_DIR/initialize_db.py,target=initialize_db.py\
    python/bin/python -m initialize_db

CMD ["./init.sh"]
