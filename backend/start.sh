#!/bin/sh
# Starts OCRIS in the cloud container (see Dockerfile). The persistent disk (DATA_DIR) is only
# there while the server runs, so the migrations are applied here and not at build time.
set -e

mkdir -p "$DATA_DIR"
python manage.py migrate --noinput
# Stops the start, with the reason in the log, when MONGO_URI is wrong or MongoDB cannot be reached
python manage.py create_indexes

# The daily backup and upkeep, next to the web server (the host's cron jobs cannot reach the disk)
python manage.py maintenance_loop &

exec gunicorn ocris_backend.wsgi:application --config gunicorn.conf.py
