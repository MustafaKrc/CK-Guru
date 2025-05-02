# shared/db_utils/job_status_utils.py
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Union, Type

from sqlalchemy.orm import Session

# Import shared models and schemas
from shared.db.models import TrainingJob, HyperparameterSearchJob, InferenceJob, JobStatusEnum
from shared.core.config import settings
from shared.db_session import get_sync_db_session # For standalone use if needed

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

# Type alias for job models
JobModel = Union[TrainingJob, HyperparameterSearchJob, InferenceJob]

def _get_job_model_class(job_type: str) -> Type[JobModel]:
    """Maps a job type string to its corresponding SQLAlchemy model class."""
    job_type_lower = job_type.lower().strip()
    if job_type_lower == 'training':
        return TrainingJob
    elif job_type_lower in ('hp_search', 'hyperparameter_search', 'hpsearch'):
        return HyperparameterSearchJob
    elif job_type_lower == 'inference':
        return InferenceJob
    else:
        raise ValueError(f"Unknown job_type string '{job_type}'")

def _get_job_instance(session: Session, job_id: int, job_type: str) -> Optional[JobModel]:
    """Fetches a specific job instance by ID and type."""
    try:
        # strip _job if present
        job_type = job_type.replace("_job", "").strip()
        # strip job if present
        job_type = job_type.replace("job", "").strip()
        model_class = _get_job_model_class(job_type)
        job = session.get(model_class, job_id)
        if not job:
             logger.error(f"Shared Util: Job {job_id} (Type: {job_type}) not found in database.")
        return job
    except ValueError: # From _get_job_model_class
        logger.error(f"Shared Util: Cannot fetch job {job_id}, unknown job type '{job_type}'.")
        return None
    except Exception as e:
        logger.error(f"Shared Util: Error fetching job {job_id} ({job_type}): {e}", exc_info=True)
        return None


def update_job_start_sync(job_id: int, job_type: str, task_id: str):
    """
    Synchronously updates job status to RUNNING, records task ID and start time.
    Uses its own session.
    """
    logger.info(f"Shared Util: Updating Job {job_id} ({job_type}) status to RUNNING (Task: {task_id}).")
    try:
        with get_sync_db_session() as session:
            job = _get_job_instance(session, job_id, job_type)
            if job:
                job.status = JobStatusEnum.RUNNING
                job.celery_task_id = task_id
                if job.started_at is None:
                    job.started_at = datetime.now(timezone.utc)
                job.status_message = "Task processing started."
                session.add(job)
                session.commit()
            # Else: error logged by _get_job_instance
    except Exception as e:
        # Log error, but don't let DB update failure stop the calling task typically
        logger.error(f"Shared Util: Failed to update START status for job {job_id} ({job_type}): {e}", exc_info=True)


def update_job_status_sync(
    job_id: int,
    job_type: str,
    status: JobStatusEnum,
    message: str,
    results: Optional[Dict] = None
):
    """
    Synchronously updates job status, message, completion time, and potentially results.
    Uses its own session.
    """
    logger.info(f"Shared Util: Updating Job {job_id} ({job_type}) status to {status.value}.")
    try:
        with get_sync_db_session() as session:
            job = _get_job_instance(session, job_id, job_type)
            if job:
                job.status = status
                job.status_message = message[:1000] # Truncate
                if status in [JobStatusEnum.SUCCESS, JobStatusEnum.FAILED, JobStatusEnum.REVOKED]:
                    job.completed_at = datetime.now(timezone.utc)

                # Add specific result fields based on the actual job instance type
                if isinstance(job, TrainingJob) and status == JobStatusEnum.SUCCESS and results:
                    job.ml_model_id = results.get('ml_model_id')
                elif isinstance(job, HyperparameterSearchJob) and status == JobStatusEnum.SUCCESS and results:
                    job.best_trial_id = results.get('best_trial_id')
                    job.best_params = results.get('best_params')
                    job.best_value = results.get('best_value')
                    job.best_ml_model_id = results.get('best_ml_model_id')
                elif isinstance(job, InferenceJob) and results and 'prediction_result' in results:
                    # Store results on SUCCESS or FAILURE (if error info is in results)
                     job.prediction_result = results.get('prediction_result')
                elif isinstance(job, InferenceJob) and status == JobStatusEnum.FAILED and not results:
                     # Ensure prediction_result is cleared or set to error state if job fails without results
                     if job.prediction_result is None or job.prediction_result.get("error") is None:
                           job.prediction_result = {"error": message[:500]} # Store truncated error

                session.add(job)
                session.commit()
            # Else: error logged by _get_job_instance
    except Exception as e:
        logger.error(f"Shared Util: Failed to update status ({status.value}) for job {job_id} ({job_type}): {e}", exc_info=True)

# --- NEW: Specific function for updating feature path ---
def update_inference_job_feature_path_sync(job_id: int, feature_path: str):
    """Synchronously updates the feature artifact path for an InferenceJob."""
    logger.info(f"Shared Util: Updating feature path for InferenceJob {job_id} to {feature_path}.")
    try:
        with get_sync_db_session() as session:
            job = _get_job_instance(session, job_id, "inference")
            if job and isinstance(job, InferenceJob): # Ensure it's the correct type
                job.feature_artifact_path = feature_path
                session.add(job)
                session.commit()
            elif job:
                 logger.error(f"Shared Util: Job {job_id} found, but is not an InferenceJob. Cannot set feature path.")
            # Else: error logged by _get_job_instance
    except Exception as e:
        logger.error(f"Shared Util: Failed to update feature path for job {job_id}: {e}", exc_info=True)