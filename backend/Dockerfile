# ===============================
# Stage 1: Build Environment
# ===============================
FROM python:3.10-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Install build tools (if needed by pip packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies to a temporary location
COPY ./backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ===============================
# Stage 2: Runtime Environment
# ===============================
FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Install runtime essentials
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy Alembic config and migrations
COPY ./backend/alembic.ini /app/alembic.ini
COPY ./backend/alembic /app/alembic

# Copy entrypoint script and make it executable
COPY ./backend/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Copy shared and backend application code
COPY ./shared /app/shared
COPY ./backend/app /app/app

# Expose port for Uvicorn (optional)
EXPOSE 8000

# Entrypoint for DB migrations and startup logic
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command to run after entrypoint
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
