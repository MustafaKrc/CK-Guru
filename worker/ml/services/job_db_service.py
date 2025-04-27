# worker/ml/services/job_db_service.py
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Union, Type
from sqlalchemy.orm import Session

from shared.db.models import TrainingJob, HyperparameterSearchJob, InferenceJob, JobStatusEnum
from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper()) 

# Helper to get the correct model class
def _get_job_model(job_type: str) -> Type[Union[TrainingJob, HyperparameterSearchJob, InferenceJob]]: # Add InferenceJob
     job_type_lower = job_type.lower() # Normalize input
     if job_type_lower == 'training':
         return TrainingJob
     elif job_type_lower in ('hp_search', 'hyperparameter_search', 'hpsearch'):
         return HyperparameterSearchJob
     elif job_type_lower == 'inference':
         return InferenceJob
     else:
         # Keep the error for truly unknown types
         raise ValueError(f"Unknown job_type '{job_type}'")

def get_job_for_worker(session: Session, job_id: int, job_type: str) -> Optional[Union[TrainingJob, HyperparameterSearchJob, InferenceJob]]:
     """Fetches a job record by ID and type."""
     model_class = _get_job_model(job_type)
     logger.debug(f"Fetching {job_type} job {job_id} for worker.")
     return session.get(model_class, job_id)

def update_job_start(session: Session, job: Union[TrainingJob, HyperparameterSearchJob, InferenceJob], task_id: str):
     """Updates job status to RUNNING and records start time/task ID."""
     job_id = job.id
     job_type_name = job.__class__.__name__ # Use class name
     logger.info(f"Updating {job_type_name} job {job_id} status to RUNNING (Task ID: {task_id})")
     job.status = JobStatusEnum.RUNNING
     job.celery_task_id = task_id # Update with the current task's ID
     # Only set started_at if it's not already set (protect against overwriting)
     if job.started_at is None:
          job.started_at = datetime.now(timezone.utc)
     job.status_message = "Task processing started." # Generic start message
     session.add(job)

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

     # Add specific result fields based on the actual job instance type
     if isinstance(job, TrainingJob) and status == JobStatusEnum.SUCCESS and results:
         job.ml_model_id = results.get('ml_model_id')
     elif isinstance(job, HyperparameterSearchJob) and status == JobStatusEnum.SUCCESS and results:
         job.best_trial_id = results.get('best_trial_id')
         job.best_params = results.get('best_params')
         job.best_value = results.get('best_value')
         job.best_ml_model_id = results.get('best_ml_model_id')
     elif isinstance(job, InferenceJob) and status == JobStatusEnum.SUCCESS and results:
         # Store the prediction result directly
         job.prediction_result = results.get('prediction_result')

     session.add(job)
     # Commit happens outside this function usually