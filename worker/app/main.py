# worker/app/main.py (Example - adjust based on your actual setup)
from celery import Celery
from .core import config 

# Define Celery App (ensure broker and backend are configured via settings)
celery_app = Celery(
    "worker",
    broker=str(config.settings.CELERY_BROKER_URL),
    backend=str(config.settings.CELERY_RESULT_BACKEND) if config.settings.CELERY_RESULT_BACKEND else None,
    include=[
        "app.tasks.ingest_repository",
        "app.tasks.dataset_generation",] 
)

# Optional Celery configuration
celery_app.conf.update(
    task_track_started=True,
    # other settings
)

if __name__ == "__main__":
    celery_app.start()