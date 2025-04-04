# worker/ingestion/app/main.py
from shared.celery_config.app import create_celery_app

# Create the Celery app instance for this specific worker
# Include the tasks module relative to this app structure
celery_app = create_celery_app(
    main_name="ingestion_worker",
    include_tasks=["app.tasks"] # Path relative to where celery worker cmd is run
)
# Optional: Add worker-specific Celery config here if needed
# celery_app.conf.update(...)