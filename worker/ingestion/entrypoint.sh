#!/bin/sh
# worker/ingestion/entrypoint.sh

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Ingestion Worker Entrypoint ---"
echo "Using Log Level: ${LOG_LEVEL}"
echo "Starting Celery worker for queue: ingestion"
echo "------------------------------------"

# Use exec to replace the shell process with the Celery process.
# This ensures signals (like SIGTERM) are passed correctly to Celery.
# Pass the log level dynamically and specify the queue.
exec celery -A app.main.celery_app worker --loglevel=${LOG_LEVEL} -Q ingestion