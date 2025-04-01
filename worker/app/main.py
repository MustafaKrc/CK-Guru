# worker/app/main.py (Example - adjust based on your actual setup)
from celery import Celery
from .core import config # Assuming config is setup

# Define Celery App (ensure broker and backend are configured via settings)
celery_app = Celery(
    "worker",
    broker=str(config.settings.CELERY_BROKER_URL),
    backend=str(config.settings.CELERY_RESULT_BACKEND), # Needs configuration!
    include=["app.tasks.repository_tasks"] # Add the module containing your tasks
)

# Optional Celery configuration
celery_app.conf.update(
    task_track_started=True,
    # other settings
)

# Import tasks (alternative way, ensures registration)
# from .tasks import repository_tasks # Uncomment if include doesn't work

if __name__ == "__main__":
    celery_app.start()