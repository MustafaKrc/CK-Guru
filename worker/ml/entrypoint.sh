#!/bin/sh
# worker/ml/entrypoint.sh

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- ML Worker Entrypoint ---"
echo "Using Log Level: ${LOG_LEVEL}"
echo "Starting Celery worker for queue: ml_queue"
echo "------------------------------------"

# Use exec to replace the shell process with the Celery process.
# Since /usr/local/bin is now first in PATH, this should find the correct celery executable.
exec python3 -m celery -A app.main.celery_app worker --loglevel=${LOG_LEVEL:-INFO} -Q ml_queue