#!/bin/bash

NAME="enterprise_service"                                 # Name of the application
DJANGODIR=/enterprise_service                 # Django project directory
VIRTUAL_ENV=entenv
CELERY_APP_NAME=enterprise_service

echo "Starting $NAME as `whoami`"

# Activate the virtual environment
source ~/.bashrc

exec python /enterprise_service/integration/crons/run_scripts/reddit_witcher.py >> /enterprise_service/logs/utils.log