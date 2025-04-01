#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Execute the main container command (passed via CMD in Dockerfile or command in docker-compose)
echo "Starting application..."
exec "$@"