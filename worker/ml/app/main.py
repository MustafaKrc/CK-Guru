# worker/ml/app/main.py
import logging
from shared.celery_config.app import create_celery_app
from shared.core.config import settings # Ensure settings are loaded

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

logger.info("ML worker starting up...")

# Create the Celery app instance for the ML worker
celery_app = create_celery_app(
    main_name="ml_worker",
    include_tasks=["app.tasks"] # Path relative to where celery worker cmd is run
)

# Optional: Add ML worker-specific Celery config here if needed
# celery_app.conf.update(
#     # Example: Set prefetch multiplier if needed for GPU tasks
#     worker_prefetch_multiplier=1,
# )

logger.info("Celery app created for ML worker.")

# Initialize Optuna storage (can be done here or lazy-loaded in tasks)
# This ensures Optuna knows about the DB URL early.
try:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.DEBUG)  
    # Check if the database URL is set
    if settings.OPTUNA_DB_URL:
        # This doesn't create tables, just configures Optuna's default storage factory
        optuna.storages.RDBStorage(url=str(settings.OPTUNA_DB_URL))
        logger.info(f"Optuna RDBStorage configured with URL from settings.")
        # Actual study creation will handle table creation if needed.
    else:
        logger.warning("OPTUNA_DB_URL not set. Optuna will use in-memory storage.")
except ImportError:
    logger.warning("Optuna library not found. Hyperparameter search features will be unavailable.")
except Exception as e:
    logger.error(f"Error configuring Optuna storage: {e}", exc_info=True)