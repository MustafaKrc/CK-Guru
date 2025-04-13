# worker/ml/services/job_db_service.py
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Union, Type
from sqlalchemy.orm import Session

from shared.db.models import TrainingJob, HyperparameterSearchJob, JobStatusEnum, MLModel # Import base models
from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper()) 

# Helper to get the correct model class
def _get_job_model(job_type: str) -> Type[Union[TrainingJob, HyperparameterSearchJob]]:
     if job_type == 'training':
         return TrainingJob
     elif job_type == 'hp_search':
         return HyperparameterSearchJob
     # Add inference later
     # elif job_type == 'inference':
     #     return InferenceJob
     else:
         raise ValueError(f"Unknown job_type '{job_type}'")

def get_job_for_worker(session: Session, job_id: int, job_type: str) -> Optional[Union[TrainingJob, HyperparameterSearchJob]]:
     """Fetches a job record by ID and type."""
     model_class = _get_job_model(job_type)
     logger.debug(f"Fetching {job_type} job {job_id} for worker.")
     return session.get(model_class, job_id)

def update_job_start(session: Session, job: Union[TrainingJob, HyperparameterSearchJob], task_id: str):
     """Updates job status to RUNNING and records start time/task ID."""
     job_id = job.id
     job_type = job.__tablename__ # Use table name to infer type
     logger.info(f"Updating {job_type} job {job_id} status to RUNNING (Task ID: {task_id})")
     job.status = JobStatusEnum.RUNNING
     job.celery_task_id = task_id
     job.started_at = datetime.now(timezone.utc)
     job.status_message = "Task processing started."
     session.add(job) # Ensure tracked
     # Commit happens outside this function usually

def update_job_completion(
     session: Session,
     job_id: int,
     job_type: str,
     status: JobStatusEnum,
     message: str,
     results: Optional[Dict] = None
 ):
     """Updates job status, message, completion time, and potentially result links."""
     model_class = _get_job_model(job_type)
     job = session.get(model_class, job_id)

     if not job:
         logger.error(f"Could not find {job_type} job {job_id} for final status update.")
         return

     logger.info(f"Updating {job_type} job {job_id} final status to {status.value}")
     job.status = status
     job.status_message = message[:1000] # Truncate
     job.completed_at = datetime.now(timezone.utc)

     # Add specific result fields based on job type
     if isinstance(job, TrainingJob) and status == JobStatusEnum.SUCCESS and results:
         job.ml_model_id = results.get('ml_model_id')
     elif isinstance(job, HyperparameterSearchJob) and status == JobStatusEnum.SUCCESS and results:
         job.best_trial_id = results.get('best_trial_id')
         job.best_params = results.get('best_params')
         job.best_value = results.get('best_value')
         job.best_ml_model_id = results.get('best_ml_model_id')
     # Add inference results later

     session.add(job)
     # Commit happens outside this function usually