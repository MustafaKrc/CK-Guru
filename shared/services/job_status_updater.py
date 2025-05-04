# shared/services/job_status_updater.py
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Union, Type, Callable

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Import models and Enums
from shared.db.models import TrainingJob, HyperparameterSearchJob, InferenceJob
from shared.schemas.enums import JobStatusEnum
from shared.core.config import settings

from shared.services.interfaces import IJobStatusUpdater, JobModel

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

class JobStatusUpdater(IJobStatusUpdater):
    """Service class for updating job statuses in the database."""

    def __init__(self, session_factory: Callable[..., Session]):
        self.session_factory = session_factory
        logger.debug("JobStatusUpdater initialized.")

    def _get_job_model_class(self, job_type_or_model: Union[str, Type[JobModel]]) -> Type[JobModel]:
        """Maps a job type string or model class to its corresponding SQLAlchemy model class."""
        if isinstance(job_type_or_model, str):
            job_type_lower = job_type_or_model.lower().strip().replace("job", "").replace("_", "")
            if job_type_lower == 'training': return TrainingJob
            if job_type_lower in ('hpsearch', 'hyperparametersearch'): return HyperparameterSearchJob
            if job_type_lower == 'inference': return InferenceJob
            raise ValueError(f"Unknown job_type string '{job_type_or_model}'")
        elif isinstance(job_type_or_model, type) and issubclass(job_type_or_model, (TrainingJob, HyperparameterSearchJob, InferenceJob)):
             return job_type_or_model # It's already a model class
        else:
             raise TypeError(f"Invalid input type for job_type_or_model: {type(job_type_or_model)}")


    def _get_and_update_job(
        self,
        job_id: int,
        job_type: Union[str, Type[JobModel]],
        updates: Dict[str, Any]
    ) -> bool:
        """Fetches a job and applies updates within a session."""
        success = False
        try:
            model_class = self._get_job_model_class(job_type)
        except (ValueError, TypeError) as e:
            logger.error(f"JobStatusUpdater: Cannot update job {job_id}, invalid job type '{job_type}': {e}")
            return False

        with self.session_factory() as session:
            try:
                job = session.get(model_class, job_id)
                if not job:
                    logger.error(f"JobStatusUpdater: Job {job_id} (Type: {model_class.__name__}) not found in database for update.")
                    return False

                logger.debug(f"JobStatusUpdater: Updating job {job_id} ({model_class.__name__}) with: {updates}")
                for field, value in updates.items():
                    if hasattr(job, field):
                        setattr(job, field, value)
                    else:
                        logger.warning(f"JobStatusUpdater: Field '{field}' not found on model {model_class.__name__} for job {job_id}.")

                session.add(job) # Add updated object to session
                session.commit()
                logger.info(f"JobStatusUpdater: Successfully updated job {job_id} ({model_class.__name__}). Status -> {updates.get('status')}")
                success = True
            except SQLAlchemyError as db_err:
                logger.error(f"JobStatusUpdater: DB error updating job {job_id} ({model_class.__name__}): {db_err}", exc_info=True)
                session.rollback()
            except Exception as e:
                logger.error(f"JobStatusUpdater: Unexpected error updating job {job_id} ({model_class.__name__}): {e}", exc_info=True)
                session.rollback() # Rollback on any error

        return success

    def update_job_start(self, job_id: int, job_type: Union[str, Type[JobModel]], task_id: str) -> bool:
        """Updates job status to RUNNING, records task ID and start time."""
        updates = {
            "status": JobStatusEnum.RUNNING,
            "celery_task_id": task_id,
            "started_at": datetime.now(timezone.utc),
            "status_message": "Task processing started.",
            "completed_at": None # Ensure completed_at is cleared if restarting
        }
        return self._get_and_update_job(job_id, job_type, updates)

    def update_job_progress(self, job_id: int, job_type: Union[str, Type[JobModel]], message: str) -> bool:
         """Updates only the status message of a job (implicitly keeps RUNNING state)."""
         updates = {
             "status_message": message[:1000] # Truncate long messages
         }
         # Note: This doesn't change the status enum. Useful for intermediate updates.
         return self._get_and_update_job(job_id, job_type, updates)

    def update_job_completion(
        self,
        job_id: int,
        job_type: Union[str, Type[JobModel]],
        status: JobStatusEnum, # Must be SUCCESS, FAILED, or REVOKED
        message: str,
        results: Optional[Dict] = None
    ) -> bool:
        """Updates job status, message, completion time, and potentially results."""
        if status not in [JobStatusEnum.SUCCESS, JobStatusEnum.FAILED, JobStatusEnum.REVOKED]:
            logger.error(f"JobStatusUpdater: Invalid final status '{status.value}' passed to update_job_completion for job {job_id}.")
            return False

        updates = {
            "status": status,
            "status_message": message[:1000], # Truncate
            "completed_at": datetime.now(timezone.utc)
        }

        # Add specific result fields based on job type
        model_class = self._get_job_model_class(job_type)
        if results:
            if model_class == TrainingJob and status == JobStatusEnum.SUCCESS:
                updates['ml_model_id'] = results.get('ml_model_id')
            elif model_class == HyperparameterSearchJob and status == JobStatusEnum.SUCCESS:
                updates['best_trial_id'] = results.get('best_trial_id')
                updates['best_params'] = results.get('best_params')
                updates['best_value'] = results.get('best_value')
                updates['best_ml_model_id'] = results.get('best_ml_model_id') # Assuming relation setup
            elif model_class == InferenceJob:
                 if 'prediction_result' in results: # Check if results contain prediction
                      updates['prediction_result'] = results.get('prediction_result')
                 elif status == JobStatusEnum.FAILED: # Store error in results if failed
                      updates['prediction_result'] = {"error": message[:500]}

        return self._get_and_update_job(job_id, model_class, updates)

    # Add specific update methods if needed, e.g., for InferenceJob feature path
    def update_inference_feature_path(self, job_id: int, feature_path: str) -> bool:
         """Updates the feature artifact path for an InferenceJob."""
         updates = {"feature_artifact_path": feature_path}
         return self._get_and_update_job(job_id, InferenceJob, updates)