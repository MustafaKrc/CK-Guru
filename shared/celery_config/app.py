# shared/celery_config/app.py
from typing import List, Optional

from celery import Celery

from shared.core.config import settings  # Import shared settings


def create_celery_app(
    main_name: str,  # e.g., 'ingestion_worker', 'dataset_worker'
    include_tasks: Optional[List[str]] = None,
) -> Celery:
    """Creates and configures a Celery application instance."""

    # Ensure backend URL is a string or None
    backend_url = (
        str(settings.CELERY_RESULT_BACKEND) if settings.CELERY_RESULT_BACKEND else None
    )

    app = Celery(
        main_name,
        broker=str(settings.CELERY_BROKER_URL),
        backend=backend_url,
        include=include_tasks or [],
    )

    # Basic Celery configuration (can be extended)
    app.conf.update(
        task_track_started=True,
        result_expires=3600,  # Keep results for 1 hour (if backend is enabled)
        broker_connection_retry_on_startup=True,
        # Add other common configurations here if needed
        # e.g., serializers:
        # task_serializer='json',
        # result_serializer='json',
        # accept_content=['json'],
    )
    return app
