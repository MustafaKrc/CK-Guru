# worker/ml/Dockerfile
# ===============================
# Single Stage Build based on CUDA image
# Multistage build had many problems with python..
# ===============================
FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Set PYTHONPATH explicitly to include /app where source code lives
ENV PYTHONPATH=/app

# Install system dependencies including Python, pip, git, build tools
# Install everything needed for runtime AND building pip packages in this stage
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3-venv \
    git \
    build-essential \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and tools using the installed python3.10
# Use python3.10 explicitly to ensure we're using the correct pip
RUN python3.10 -m pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements BEFORE application code to leverage Docker caching better
COPY ./worker/ml/requirements.txt /app/worker/ml/requirements.txt
# Copy shared requirements if they exist and are needed for install (unlikely now)
# COPY ./shared/requirements.txt /app/shared/requirements.txt
# RUN python3.10 -m pip install --no-cache-dir -r /app/shared/requirements.txt

# Install Python dependencies directly into the system Python site-packages
# This ensures celery command is installed relative to the python3.10 we execute
RUN python3.10 -m pip install --no-cache-dir -r /app/worker/ml/requirements.txt

# Example: How to install GPU PyTorch (Uncomment and adjust when needed in Phase 2)
# RUN python3.10 -m pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121


# Copy shared code and ML worker specific code AFTER pip install
COPY ./shared /app/shared
COPY ./worker/ml/app /app/app
COPY ./worker/ml/services /app/services

# Copy and set permissions for the entrypoint script
COPY ./worker/ml/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Set the ENTRYPOINT
ENTRYPOINT ["/app/entrypoint.sh"]