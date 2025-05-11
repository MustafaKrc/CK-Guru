# backend/app/core/celery_app.py
from shared.celery_config.app import create_celery_app

# Create the backend app instance - it doesn't need 'include' as it only sends
backend_celery_app = create_celery_app(main_name="backend_sender")

# Ensure result backend is enabled if tasks endpoint needs it
if not backend_celery_app.conf.result_backend:
    # Log warning or raise error depending on requirements
    import logging

    logging.getLogger(__name__).warning(
        "Celery result backend is not configured for the backend sender. Task status polling will not work."
    )
