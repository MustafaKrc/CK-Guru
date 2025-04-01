# Use an official Python runtime as a parent image
FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Even if WORKDIR adds it implicitly, this makes finding shared_db reliable.
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Install system dependencies
# Add bash for entrypoint script, git if needed by core logic, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Install pip requirements
# Copy requirements first for better layer caching
COPY ./backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt


# Copy alembic config and migrations from project root (adjust if paths differ)
COPY ./backend/alembic.ini /app/alembic.ini
COPY ./backend/alembic /app/alembic
# Copy the entrypoint script from project root
COPY ./backend/entrypoint.sh /app/entrypoint.sh
# Make entrypoint executable within the container image
RUN chmod +x /app/entrypoint.sh

# Copy shared code from project root
COPY ./shared /app/shared

# Copy backend application code
COPY ./backend/app /app/app

# Expose the port the app runs on (if applicable, backend needs this)
EXPOSE 8000

# --- Set Entrypoint and Default CMD ---
# Use the entrypoint script to handle startup logic (like migrations)
ENTRYPOINT ["/app/entrypoint.sh"]

# Define the default command to run AFTER the entrypoint script finishes migrations
# This will be passed as "$@" to entrypoint.sh
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]