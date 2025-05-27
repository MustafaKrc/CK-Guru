# shared/services/job_status_updater.py
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Type, Union

from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from shared.core.config import settings

# Import models and Enums
from shared.db.models import (  # Add Dataset
    Dataset,
    HyperparameterSearchJob,
    InferenceJob,
    TrainingJob,
)
from shared.db.models.dataset import DatasetStatusEnum
from shared.schemas.enums import (  # Add DatasetStatusEnum
    JobStatusEnum,
)
from shared.services.interfaces import IJobStatusUpdater, JobModel

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


class JobStatusUpdater(IJobStatusUpdater):
    """Service class for updating job/dataset statuses in the database."""

    def __init__(self, session_factory: Callable[..., Session]):
        self.session_factory = session_factory
        logger.debug("JobStatusUpdater initialized.")

    def _get_job_model_class(
        self, job_type_or_model: Union[str, Type[JobModel]]
    ) -> Type[JobModel]:
        """Maps a job type string or model class to its corresponding SQLAlchemy model class."""
        if isinstance(job_type_or_model, str):
            job_type_lower = (
                job_type_or_model.lower().strip().replace("job", "").replace("_", "")
            )
            if job_type_lower == "training":
                return TrainingJob
            if job_type_lower in ("hpsearch", "hyperparametersearch"):
                return HyperparameterSearchJob
            if job_type_lower == "inference":
                return InferenceJob
            if job_type_lower == "dataset":
                return Dataset  # Add Dataset mapping
            raise ValueError(f"Unknown job_type string '{job_type_or_model}'")
        # Include Dataset in the issubclass check
        elif isinstance(job_type_or_model, type) and issubclass(
            job_type_or_model,
            (TrainingJob, HyperparameterSearchJob, InferenceJob, Dataset),
        ):
            return job_type_or_model  # It's already a model class
        else:
            raise TypeError(
                f"Invalid input type for job_type_or_model: {type(job_type_or_model)}"
            )

    def _get_and_update_job(
        self, job_id: int, job_type: Union[str, Type[JobModel]], updates: Dict[str, Any]
    ) -> bool:
        """Fetches a job/dataset and applies updates within a session."""
        success = False
        model_class: Type[JobModel] | None = None
        try:
            model_class = self._get_job_model_class(job_type)
        except (ValueError, TypeError) as e:
            logger.error(
                f"JobStatusUpdater: Cannot update job {job_id}, invalid job type '{job_type}': {e}"
            )
            return False

        with self.session_factory() as session:
            try:
                job = session.get(model_class, job_id)
                if not job:
                    logger.error(
                        f"JobStatusUpdater: Job/Dataset {job_id} (Type: {model_class.__name__}) not found in database for update."
                    )
                    return False

                logger.debug(
                    f"JobStatusUpdater: Updating {model_class.__name__} {job_id} with: {updates}"
                )

                # Manually add updated_at for sync session consistency
                updates["updated_at"] = datetime.now(timezone.utc)

                for field, value in updates.items():
                    if hasattr(job, field):
                        setattr(job, field, value)
                    else:
                        logger.warning(
                            f"JobStatusUpdater: Field '{field}' not found on model {model_class.__name__} for ID {job_id}."
                        )

                session.add(job)  # Add updated object to session
                session.commit()
                logger.info(
                    f"JobStatusUpdater: Successfully updated {model_class.__name__} ID {job_id}. Status -> {updates.get('status')}"
                )
                success = True
            except SQLAlchemyError as db_err:
                logger.error(
                    f"JobStatusUpdater: DB error updating {model_class.__name__} {job_id}: {db_err}",
                    exc_info=True,
                )
                session.rollback()
            except Exception as e:
                logger.error(
                    f"JobStatusUpdater: Unexpected error updating {model_class.__name__} {job_id}: {e}",
                    exc_info=True,
                )
                session.rollback()  # Rollback on any error

        return success

    # --- Generic Job Updates ---

    def update_job_start(
        self, job_id: int, job_type: Union[str, Type[JobModel]], task_id: str
    ) -> bool:
        """Updates job/dataset status to RUNNING/GENERATING, records task ID and start time."""
        model_class = self._get_job_model_class(job_type)
        # Determine the correct 'running' status enum based on model type
        running_status = (
            DatasetStatusEnum.GENERATING
            if model_class is Dataset
            else JobStatusEnum.RUNNING
        )

        updates = {
            "status": running_status,
            "celery_task_id": task_id,
            "started_at": datetime.now(timezone.utc),
            "status_message": "Task processing started.",
            "completed_at": None,  # Ensure completed_at is cleared if restarting
        }
        # Clear specific result fields if restarting
        if model_class is InferenceJob:
            updates["prediction_result"] = None
        elif model_class is Dataset:
            updates["storage_path"] = None
            updates["background_data_path"] = None
        elif model_class is HyperparameterSearchJob:
            updates["best_trial_id"] = None
            updates["best_params"] = None
            updates["best_value"] = None
            updates["best_ml_model_id"] = None

        return self._get_and_update_job(job_id, job_type, updates)

    def update_job_progress(
        self, job_id: int, job_type: Union[str, Type[JobModel]], message: str
    ) -> bool:
        """Updates only the status message of a job/dataset."""
        updates = {"status_message": message[:1000]}  # Truncate long messages
        # Note: This doesn't change the status enum. Useful for intermediate updates.
        return self._get_and_update_job(job_id, job_type, updates)

    def update_job_completion(
        self,
        job_id: int,
        job_type: Union[str, Type[JobModel]],
        status: Union[JobStatusEnum, DatasetStatusEnum],  # Allow either enum
        message: str,
        results: Optional[Dict] = None,
    ) -> bool:
        """Updates final job/dataset status, message, completion time, and potentially results."""
        model_class = self._get_job_model_class(job_type)

        # Validate final status based on model type
        valid_job_statuses = [
            JobStatusEnum.SUCCESS,
            JobStatusEnum.FAILED,
            JobStatusEnum.REVOKED,
        ]
        valid_dataset_statuses = [DatasetStatusEnum.READY, DatasetStatusEnum.FAILED]

        if model_class is Dataset:
            if status not in valid_dataset_statuses:
                logger.error(
                    f"JobStatusUpdater: Invalid final status '{status}' for Dataset job {job_id}."
                )
                return False
        else:  # Training, HP, Inference jobs
            if status not in valid_job_statuses:
                logger.error(
                    f"JobStatusUpdater: Invalid final status '{status}' for Job {job_id}."
                )
                return False

        updates = {
            "status": status,
            "status_message": message[:1000],  # Truncate
            "completed_at": datetime.now(timezone.utc),
        }

        # Add specific result fields based on job type and success
        if results:
            is_success = (
                model_class is Dataset and status == DatasetStatusEnum.READY
            ) or (model_class is not Dataset and status == JobStatusEnum.SUCCESS)

            if is_success:
                if model_class == TrainingJob:
                    updates["ml_model_id"] = results.get("ml_model_id")
                elif model_class == HyperparameterSearchJob:
                    updates["best_trial_id"] = results.get("best_trial_id")
                    updates["best_params"] = results.get("best_params")
                    updates["best_value"] = results.get("best_value")
                    updates["best_ml_model_id"] = results.get("best_ml_model_id")
                elif model_class == InferenceJob:
                    updates["prediction_result"] = results.get("prediction_result")
                elif model_class == Dataset:
                    updates["storage_path"] = results.get("storage_path")
                    updates["background_data_path"] = results.get(
                        "background_data_path"
                    )
                    updates["num_rows"] = results.get("num_rows")
            elif model_class == InferenceJob and status == JobStatusEnum.FAILED:
                # Store error in prediction_result for inference jobs on failure
                updates["prediction_result"] = {"error": message[:500]}

        return self._get_and_update_job(job_id, model_class, updates)

    # --- Specific Updates (if needed, easier than adding to generic completion results) ---

    def update_inference_feature_path(self, job_id: int, feature_path: str) -> bool:
        """Updates the feature artifact path for an InferenceJob."""
        updates = {
            "feature_artifact_path": feature_path
        }  # Field needs adding to InferenceJob model
        # Check if the field exists before updating
        if not hasattr(InferenceJob, "feature_artifact_path"):
            logger.error(
                "Field 'feature_artifact_path' does not exist on InferenceJob model. Cannot update."
            )
            return False
        return self._get_and_update_job(job_id, InferenceJob, updates)

    # Add specific dataset methods leveraging the generic update method
    def update_dataset_start(self, dataset_id: int, task_id: str) -> bool:
        """Sets Dataset status to GENERATING."""
        return self.update_job_start(dataset_id, Dataset, task_id)

    def update_dataset_progress(self, dataset_id: int, message: str) -> bool:
        """Updates Dataset status message."""
        return self.update_job_progress(dataset_id, Dataset, message)

    def update_dataset_completion(
        self,
        dataset_id: int,
        status: DatasetStatusEnum,
        message: str,
        storage_path: Optional[str] = None,
        background_data_path: Optional[str] = None,
        num_rows: Optional[int] = None,
    ) -> bool:
        """Updates final Dataset status and paths."""
        results = {}
        if status == DatasetStatusEnum.READY:
            if storage_path:
                results["storage_path"] = storage_path
            if background_data_path:
                results["background_data_path"] = background_data_path
            if num_rows:
                results["num_rows"] = num_rows
        return self.update_job_completion(dataset_id, Dataset, status, message, results)
