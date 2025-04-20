# worker/ingestion/app/main.py
import logging
from shared.celery_config.app import create_celery_app
from shared.core.config import settings # Ensure settings are loaded

# Use standard logging configuration
logging.basicConfig(level=settings.LOG_LEVEL.upper())
logger = logging.getLogger(__name__)

logger.info("Ingestion worker starting up...")
logger.info(f"Log Level: {settings.LOG_LEVEL}")
logger.info(f"Broker URL: {settings.CELERY_BROKER_URL}")
logger.info(f"Result Backend: {'Configured' if settings.CELERY_RESULT_BACKEND else 'Not Configured'}")

# Create the Celery app instance for this specific worker
# Include the tasks module relative to this app structure
celery_app = create_celery_app(
    main_name="ingestion_worker",
    include_tasks=["app.tasks"] # Path relative to where celery worker cmd is run
)
# Optional: Add worker-specific Celery config here if needed
# celery_app.conf.update(...)

logger.info("Celery app created for ingestion worker.")