# ===============================
# Stage 1: Build Environment
# ===============================
FROM python:3.10-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Install system deps 
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip, setuptools, and wheel
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy shared and worker requirements
COPY ./shared /app/shared
COPY ./worker/dataset/requirements.txt /app/worker/dataset/requirements.txt

# Install dependencies into /install
RUN pip install --no-cache-dir --prefix=/install -r /app/worker/dataset/requirements.txt

# ===============================
# Stage 2: Final Runtime Image
# ===============================
FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Install runtime dependencies (e.g., bash, git if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies from builder
COPY --from=builder /install /usr/local

# Copy your app code
COPY ./shared /app/shared
COPY ./worker/dataset/app /app/app
COPY ./worker/dataset/services /app/services

# Copy and set permissions for the entrypoint script
COPY ./worker/dataset/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Set the ENTRYPOINT
ENTRYPOINT ["/app/entrypoint.sh"]
