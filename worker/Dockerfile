# Choose an official NVIDIA CUDA base image
# Select a version compatible with your ML framework (PyTorch/TensorFlow) and host driver
# Example using CUDA 11.8 with cuDNN 8 on Ubuntu 22.04
# Check compatibility: https://pytorch.org/get-started/locally/ , https://www.tensorflow.org/install/gpu
# Using '-runtime' is usually sufficient unless your build process needs the full toolkit ('-devel')
FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04

# Set environment variables to avoid interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

ENV PYTHONPATH="${PYTHONPATH}:/app"

# Install Python, pip, git (often needed for ML packages or cloning) and other essentials
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3-venv \
    git \
    openjdk-17-jre-headless \
    # Add any other system dependencies your ML or data processing code might need
    && rm -rf /var/lib/apt/lists/*

# Make python3 point to python3.10 (if needed, Ubuntu might default differently)
# RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1

# Upgrade pip and install essentials
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel

# Set work directory
WORKDIR /app

COPY ./third_party/ck-0.7.0/ck-0.7.0-jar-with-dependencies.jar /app/third_party/ck.jar

# Install Python dependencies
# Copy requirements first to leverage Docker cache
COPY ./worker/requirements.txt .
# IMPORTANT: Ensure your requirements.txt specifies GPU-enabled versions
# e.g., for PyTorch: find the correct command from https://pytorch.org/get-started/locally/
# RUN pip3 install --no-cache-dir -r requirements.txt -f https://download.pytorch.org/whl/cu118/torch_stable.html
# OR for TensorFlow: pip install tensorflow[and-cuda] (check specific TF version docs)
RUN pip3 install --no-cache-dir -r requirements.txt
# Add specific ML library install commands here if they need special handling for CUDA

# Copy the shared code from the project root
COPY ./shared /app/shared

# Copy the worker application code
COPY ./worker/app /app/app

# Command to run the Celery worker
# Adjust 'app.main.celery_app' to match your Celery app instance location
CMD ["celery", "-A", "app.main.celery_app", "worker", "--loglevel=info"]