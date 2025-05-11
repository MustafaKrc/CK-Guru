# worker/ml/services/handlers/base_handler.py
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from celery import Task

# --- Concrete Service types  ---
from services.artifact_service import ArtifactService

# Import shared components
from shared.core.config import settings

# --- Concrete Repository types for injection type hints ---
from shared.repositories import (
    MLFeatureRepository,
    ModelRepository,
    XaiResultRepository,
)
from shared.services import JobStatusUpdater
from shared.utils.task_utils import update_task_state

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
        task_instance: Task,
        # --- Inject Concrete Implementations ---
        # (Type hint with interfaces where they exist, but note provider gives concrete)
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

    def _update_progress(self, message: str, progress: int, state: str = "STARTED"):
        """Helper to update Celery task state."""
        if self.task:
            logger.debug(
                f"Updating task {self.task.request.id} progress: {progress}%, State: {state}, Msg: {message}"
            )
            try:
                update_task_state(self.task, state, message, progress)
            except Exception as e:
                logger.error(f"Failed to update Celery task state: {e}", exc_info=True)
        else:
            logger.warning("Task instance not available for progress update.")

    # --- Removed _update_db_status - use self.status_updater directly ---

    # Define the main execution method for subclasses to implement
    @abstractmethod
    def process_job(self) -> Dict:
        """
        Main method to orchestrate the specific job processing logic.
        Must be implemented by subclasses.
        Should return a dictionary summarizing the result for the Celery task.
        """
        pass
