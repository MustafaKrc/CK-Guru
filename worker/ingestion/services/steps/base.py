# worker/ingestion/services/steps/base.py
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pathlib import Path
import git
from celery import Task
from shared.core.config import settings 
from shared.schemas.ingestion_data import CommitGuruMetricPayload, CKMetricPayload
from shared.utils.task_utils import update_task_state

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

class IngestionContext:
    """Holds state shared between ingestion steps."""
    # Input Parameters
    repository_id: int
    git_url: str
    repo_local_path: Path

    # Task Management
    task_instance: Optional[Task] = None
    warnings: List[str]

    # Processing State & Data
    repo_object: Optional[git.Repo] = None
    raw_commit_guru_data: List[CommitGuruMetricPayload]          # Raw data from calculate_commit_guru_metrics util
    commit_hash_to_db_id_map: Dict[str, int]  # Map commit hash to DB ID after persistence
    commit_fix_keyword_map: Dict[str, bool]   # Map commit hash to 'fix' keyword presence
    bug_link_map_hash: Dict[str, List[str]]   # Map buggy_hash -> [fixing_hash1, ...]
    raw_ck_metrics: Dict[str, List[CKMetricPayload]]   # commit_hash -> DataFrame of CK metrics for that commit
    inserted_guru_metrics_count: int
    inserted_ck_metrics_count: int

    is_single_commit_mode: bool             # Flag for operation mode
    target_commit_hash: Optional[str] = None # Specific commit for single mode or general tracking
    parent_commit_hash: Optional[str] = None # Determined parent hash for single mode
    inference_job_id: Optional[int] = None   # Link back to inference job
    # Flag to indicate if parent metrics existed/were calculated (used in single mode)
    parent_metrics_processed: bool = False
    # Holder for combined features in single mode before passing to ML worker
    final_combined_features: Optional[List[Dict[str, Any]]] = None # Changed from Dict to List[Dict]


    def __init__(
        self,
        repository_id: int,
        repo_local_path: Path,
        task_instance: Task,
        git_url: Optional[str] = None,
        is_single_commit_mode: bool = False,
        target_commit_hash: Optional[str] = None,
        parent_commit_hash: Optional[str] = None,
        inference_job_id: Optional[int] = None,
        final_combined_features: Optional[List[Dict[str, Any]]] = None # Keep this as dict for now
    ):
        self.repository_id = repository_id
        self.git_url = git_url
        self.repo_local_path = repo_local_path
        self.task_instance = task_instance
        self.is_single_commit_mode = is_single_commit_mode
        self.target_commit_hash = target_commit_hash
        self.parent_commit_hash = parent_commit_hash
        self.inference_job_id = inference_job_id
        self.final_combined_features = final_combined_features
        self.warnings = []
        self.repo_object = None
        # Initialize with correct empty types
        self.raw_commit_guru_data: List[CommitGuruMetricPayload] = []
        self.commit_hash_to_db_id_map = {}
        self.commit_fix_keyword_map = {}
        self.bug_link_map_hash = {}
        self.raw_ck_metrics: Dict[str, List[CKMetricPayload]] = {}
        self.inserted_guru_metrics_count = 0
        self.inserted_ck_metrics_count = 0
        self.parent_metrics_processed = False


class IngestionStep(ABC):
    """Abstract base class for an ingestion pipeline step."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Returns the user-friendly name of the step."""
        pass

    @abstractmethod
    def execute(self, context: IngestionContext, **kwargs: Any) -> IngestionContext:
        """
        Executes the logic for this step.

        Args:
            context: The shared IngestionContext object.
            **kwargs: Injected dependencies (e.g., repositories, services).

        Returns:
            The updated IngestionContext object.

        Raises:
            Exception: If a critical error occurs that should stop the pipeline.
                       Non-critical errors should add warnings to context.warnings.
        """
        pass

    def _update_progress(self, context: IngestionContext, message: str, progress: int, warning: Optional[str] = None):
        """Helper to update Celery task progress via the context."""
        if context.task_instance:
            update_task_state(context.task_instance, 'STARTED', message, progress, warning)

    def _log_info(self, context: IngestionContext, message: str):
        """Helper for consistent logging prefix."""
        task_id = context.task_instance.request.id if context.task_instance else 'N/A'
        logger.info(f"Task {task_id} - Step [{self.name}]: {message}")

    def _log_warning(self, context: IngestionContext, message: str):
        """Helper for consistent logging prefix and adding to context warnings."""
        task_id = context.task_instance.request.id if context.task_instance else 'N/A'
        logger.warning(f"Task {task_id} - Step [{self.name}]: {message}")
        context.warnings.append(f"[{self.name}] {message}")

    def _log_error(self, context: IngestionContext, message: str, exc_info=True):
        """Helper for consistent error logging prefix."""
        task_id = context.task_instance.request.id if context.task_instance else 'N/A'
        logger.error(f"Task {task_id} - Step [{self.name}]: {message}", exc_info=exc_info)

    def _log_debug(self, context: IngestionContext, message: str):
        """Helper for consistent debug logging prefix."""
        task_id = context.task_instance.request.id if context.task_instance else 'N/A'
        logger.debug(f"Task {task_id} - Step [{self.name}]: {message}")