# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install dependencies
# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend application code
COPY ./app /app/app

# Copy the shared core logic (adjust path if needed relative to context)
# Assumes docker-compose builds with context set to project root, or copy manually before build
COPY ../core_logic /app/core_logic

# Expose port 8000 for FastAPI
EXPOSE 8000

# Command to run the Uvicorn server
# Adjust module path if your FastAPI instance ('app') is located differently
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
# Use "--reload" only for development, remove for production builds