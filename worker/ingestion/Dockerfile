# ===============================
# Stage 1: Build Environment
# ===============================
FROM python:3.10-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Install build dependencies for Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirement file and install into custom directory
COPY ./worker/ingestion/requirements.txt /app/worker/ingestion/requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r /app/worker/ingestion/requirements.txt

# ===============================
# Stage 2: Final Runtime Image
# ===============================
FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Install only required runtime tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    git \
    openjdk-21-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Copy CK jar
COPY ./third_party/ck-0.7.0/ck-0.7.0-jar-with-dependencies.jar /app/third_party/ck.jar

# Copy shared and app code
COPY ./shared /app/shared
COPY ./worker/ingestion/app /app/app
COPY ./worker/ingestion/services /app/services

# Copy and set permissions for the entrypoint script
COPY ./worker/ingestion/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Set the ENTRYPOINT
ENTRYPOINT ["/app/entrypoint.sh"]
