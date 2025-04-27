# worker/ingestion/services/job_db_service.py
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Union, Type
from sqlalchemy.orm import Session

# Import relevant models and schemas
from shared.db.models import InferenceJob
from shared.schemas.enums import JobStatusEnum
from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

# Maybe merge this with ML worker's job_db_service if structure allows

def update_inference_job_status(
    session: Session,
    inference_job_id: int,
    status: JobStatusEnum,
    message: str,
    celery_task_id: Optional[str] = None, # Optionally update task ID
    is_start: bool = False # Flag if this is the start update
):
    """Updates the status and message of an InferenceJob."""
    job = session.get(InferenceJob, inference_job_id)
    if not job:
        logger.error(f"Could not find InferenceJob {inference_job_id} for status update.")
        return

    logger.info(f"Updating InferenceJob {inference_job_id} status to {status.value}. Message: {message[:100]}...")
    job.status = status
    job.status_message = message[:1000] # Truncate

    if celery_task_id:
        job.celery_task_id = celery_task_id
    if is_start and job.started_at is None: # Only set started_at once
        job.started_at = datetime.now(timezone.utc)
    if status in [JobStatusEnum.SUCCESS, JobStatusEnum.FAILED, JobStatusEnum.REVOKED]:
        job.completed_at = datetime.now(timezone.utc)

    session.add(job)
    # Commit is handled by the caller (e.g., context manager in task)