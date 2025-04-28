#!/bin/sh
# worker/ml/entrypoint.sh

# Exit immediately if a command exits with a non-zero status.
set -e

# Default queues if not passed as argument
QUEUES=${1:-ml_queue,xai_queue} # Default to both if no arg given

echo "--- ML Worker Entrypoint ---"
echo "Using Log Level: ${LOG_LEVEL:-INFO}"
echo "Starting Celery worker for queue(s): ${QUEUES}"
echo "------------------------------------"

# Use exec, pass queues, maybe set concurrency
# Example: setting concurrency to 1 for GPU tasks on ml_queue, maybe higher for xai_queue if separate worker
exec python3 -m celery -A app.main.celery_app worker --loglevel=${LOG_LEVEL:-INFO} -Q ${QUEUES} -c 1