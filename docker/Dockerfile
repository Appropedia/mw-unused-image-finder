#Stage for building custom sqlite3 extensions
#---------------------------------------------------------------------------------------------------
FROM alpine:latest AS extension_builder

RUN apk add make gcc libc-dev sqlite-dev
COPY sqlite_extensions sqlite_extensions/
RUN make -C sqlite_extensions

#Final stage
#---------------------------------------------------------------------------------------------------
FROM alpine:latest

#Install dependencies
RUN apk add python3
RUN apk add imagemagick
RUN apk add libjpeg-turbo

#Change to the installation directory
ARG APP_NAME="mw-cleanup-assistant"
WORKDIR /$APP_NAME

#Setup the python virtual environment
ENV PYTHONUNBUFFERED=1
RUN --mount=source=setup-python.sh,target=setup-python.sh ./setup-python.sh
RUN python/bin/pip install gunicorn

#Set up crond to run the update and bot scripts at their respective moments
RUN cat <<EOF >> /etc/crontabs/root
@reboot                                 /$APP_NAME/update_images.sh
*/5     *       *       *       *       /$APP_NAME/update_images.sh
*/1     *       *       *       *       /$APP_NAME/mediawiki_bot.sh
EOF

#This wrapper script runs the image update script while preventing concurrent execution
RUN cat <<EOF > update_images.sh && chmod +x update_images.sh
cd /$APP_NAME
flock -x -n "/run/lock/update_images.lock" -c "python/bin/python -m update_images"
EOF

#This wrapper script runs the mediawiki bot script while preventing concurrent execution
RUN cat <<EOF > mediawiki_bot.sh && chmod +x mediawiki_bot.sh
cd /$APP_NAME
flock -x -n "/run/lock/mediawiki_bot.lock" -c "python/bin/python -m mediawiki_bot"
EOF

#This wrapper script runs all processes in the container
RUN cat <<EOF > /$APP_NAME/init.sh && chmod +x /$APP_NAME/init.sh
#!/bin/sh

#Start cron in foreground mode, so the image update script log can be captured
crond -f &

#The gunicorn server will run at internal port 80
python/bin/gunicorn app:app -b 0.0.0.0:80 &

#Wait for any process to exit and return the status code of the process that exited first
wait -n
exit $?
EOF

#Install the server application files
COPY app.py update_images.py mediawiki_bot.py ./
COPY setup-admin-account.py regenerate_user_password.py ./
COPY modules modules/
COPY templates templates/
COPY assets assets/
COPY --from=extension_builder sqlite_extensions/*.so sqlite_extensions/

#Set up a volume for the database
RUN mkdir /var/lib/$APP_NAME
VOLUME /var/lib/$APP_NAME

#Initialize the sqlite3 database by running the corresponding script with a temporary configuration
#that specifies its location
RUN --mount=source=initialize_db.py,target=initialize_db.py <<EOF
cat <<CONFIG_EOF > config.toml
[sqlite3]
path = '/var/lib/$APP_NAME/db.sqlite3'
CONFIG_EOF

python/bin/python -B -m initialize_db

rm config.toml
EOF

CMD ["./init.sh"]
