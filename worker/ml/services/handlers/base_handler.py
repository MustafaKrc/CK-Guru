# worker/ml/services/handlers/base_handler.py
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

# --- Concrete Service types  ---
from services.artifact_service import ArtifactService
from shared.celery_config.base_task import EventPublishingTask

# Import shared components
from shared.core.config import settings

# --- Concrete Repository types for injection type hints ---
from shared.repositories import (
    MLFeatureRepository,
    ModelRepository,
    XaiResultRepository,
)
from shared.services import JobStatusUpdater

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


class BaseMLJobHandler(ABC):
    """
    Abstract base class for handling ML jobs (Training, HP Search, Inference).
    Focuses on holding job info and injected dependencies. Core logic in subclasses.
    """

    def __init__(
        self,
        job_id: int,
        task_instance: EventPublishingTask,
        status_updater: JobStatusUpdater,
        model_repo: ModelRepository,
        xai_repo: XaiResultRepository,
        feature_repo: MLFeatureRepository,
        artifact_service: ArtifactService,
    ):
        """Initializes the handler with job info and concrete dependencies."""
        self.job_id = job_id
        self.task = task_instance
        self.job_db_record: Any = (
            None  # Holds the specific DB job record (loaded by subclass)
        )
        self.job_config: Dict[str, Any] = {}
        self.dataset_id: Optional[int] = None

        # --- Store Injected Concrete Dependencies ---
        self.status_updater: JobStatusUpdater = status_updater
        self.model_repo: ModelRepository = model_repo
        self.xai_repo: XaiResultRepository = xai_repo
        self.feature_repo: MLFeatureRepository = feature_repo
        self.artifact_service: ArtifactService = artifact_service

        logger.debug(
            f"Initialized {self.__class__.__name__} for Job ID {job_id}, Task ID {self.task.request.id if self.task else 'N/A'}"
        )

    @property
    @abstractmethod
    def job_type_name(self) -> str:
        """Returns the specific job type name (e.g., 'TrainingJob')."""
        pass

    @property
    @abstractmethod
    def job_model_class(self) -> type:
        """Returns the SQLAlchemy model class for the specific job type."""
        pass

        """Helper to update Celery task state."""

    async def _update_progress(
        self, message: str, progress: int, state: str = "STARTED"
    ):
        if self.task:
            logger.debug(
                f"Task {self.task.request.id} (Job {self.job_id}): Progress {progress}%, State: {state}, Msg: {message}"
            )
            try:
                # Determine event context. These should ideally be set on self or passed if dynamic per job.
                # For ML jobs, entity_id is self.job_id, entity_type is self.job_type_name
                # job_type for SSE could be more specific than just self.job_type_name
                # e.g., "model_training", "hp_search", "model_inference", "xai_generation"

                # Simplified example: job_type for SSE event can be determined based on handler class
                # or a more specific attribute on the handler.
                sse_job_type = self.job_type_name  # Default, can be refined
                # if "TrainingJobHandler" in self.__class__.__name__: sse_job_type = "model_training"
                # elif "HPSearchJobHandler" in self.__class__.__name__: sse_job_type = "hp_search"
                # elif "InferenceJobHandler" in self.__class__.__name__: sse_job_type = "model_inference"
                # elif "XAIExplanationHandler" in self.__class__.__name__: sse_job_type = "xai_generation"
                # elif "XAIOrchestrationHandler" in self.__class__.__name__: sse_job_type = "xai_orchestration"

                await self.task.update_task_state(  # CHANGED to await
                    state=state,
                    status_message=message,
                    progress=progress,
                    job_type=sse_job_type,
                    entity_id=self.job_id,
                    entity_type=self.job_type_name,  # e.g., "TrainingJob", "HPSearchJob"
                    # user_id if available
                    meta={
                        "progress": progress,
                        "status_message": message,
                    },  # For Celery backend
                )
            except Exception as e:
                logger.error(
                    f"Failed to update Celery task state for job {self.job_id}: {e}",
                    exc_info=True,
                )
        else:
            logger.warning(
                f"Task instance not available for progress update on job {self.job_id}."
            )

    # --- Removed _update_db_status - use self.status_updater directly ---

    # Define the main execution method for subclasses to implement
    @abstractmethod
    async def process_job(self) -> Dict:
        """
        Main method to orchestrate the specific job processing logic.
        Must be implemented by subclasses.
        Should return a dictionary summarizing the result for the Celery task.
        """
        pass
