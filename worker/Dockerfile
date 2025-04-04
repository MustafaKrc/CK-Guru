# ===============================
# Stage 1: Build Stage
# ===============================
FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="${PYTHONPATH}:/app"

WORKDIR /app

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3-venv \
    git \
    build-essential \
    openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and tools
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements and install them to a separate path
COPY ./worker/requirements.txt /app/requirements.txt

# Example: Uncomment if using PyTorch with CUDA
# RUN pip3 install --no-cache-dir -r requirements.txt -f https://download.pytorch.org/whl/cu118/torch_stable.html

RUN pip3 install --no-cache-dir --prefix=/install -r /app/requirements.txt

# ===============================
# Stage 2: Runtime Stage
# ===============================
FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="${PYTHONPATH}:/app"

WORKDIR /app

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    openjdk-17-jre-headless \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from the builder
COPY --from=builder /install /usr/local

# Copy CK jar
COPY ./third_party/ck-0.7.0/ck-0.7.0-jar-with-dependencies.jar /app/third_party/ck.jar

# Copy application code
COPY ./shared /app/shared
COPY ./worker/app /app/app

# Final entrypoint
CMD ["celery", "-A", "app.main.celery_app", "worker", "--loglevel=info"]
