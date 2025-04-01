# backend/app/core/celery_app.py
from celery import Celery
from .config import settings # Import your backend settings

# Define a Celery app instance configured for the backend's use
# It connects to the same broker and result backend as the worker
backend_celery_app = Celery(
    "backend_tasks", # Give it a distinct name (doesn't affect task routing)
    broker=str(settings.CELERY_BROKER_URL),
    backend=str(settings.CELERY_RESULT_BACKEND),
    # Important: Set ignore_result=False if you want results/status
    # (Celery default is True if no backend is specified, but explicit is good)
    # By default, this instance doesn't need to know about task implementations
    # include=[] # No need to include worker task modules here
)

# Optional: Update with specific backend settings if needed
# backend_celery_app.conf.update(...)

# Note: This instance does NOT run tasks, it only sends them and checks results.