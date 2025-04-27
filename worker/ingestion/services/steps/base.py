# worker/ingestion/services/steps/base.py
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set
from pathlib import Path
import pandas as pd
import git
from sqlalchemy.orm import Session
from celery import Task
from shared.db.models import CommitGuruMetric, CKMetric # Example imports
from shared.core.config import settings # Import settings if needed for logging level

logger = logging.getLogger(__name__)
# Set level from settings if available, otherwise default
log_level = getattr(settings, 'LOG_LEVEL', 'INFO')
logger.setLevel(log_level.upper())

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
    raw_commit_guru_data: List[Dict]          # Raw data from calculate_commit_guru_metrics util
    commit_hash_to_db_id_map: Dict[str, int]  # Map commit hash to DB ID after persistence
    commit_fix_keyword_map: Dict[str, bool]   # Map commit hash to 'fix' keyword presence
    bug_link_map_hash: Dict[str, List[str]]   # Map buggy_hash -> [fixing_hash1, ...]
    raw_ck_metrics: Dict[str, pd.DataFrame]   # commit_hash -> DataFrame of CK metrics for that commit
    inserted_guru_metrics_count: int
    inserted_ck_metrics_count: int
    target_commit_hash: Optional[str] = None # The specific commit to process
    parent_commit_hash: Optional[str] = None # Determined parent hash
    # Flag to indicate if parent metrics existed or were calculated in this run
    parent_metrics_processed: bool = False
    # Store the ID of the overarching InferenceJob
    inference_job_id: Optional[int] = None

    def __init__(self, repository_id: int, git_url: str, repo_local_path: Path, task_instance: Task,
                 target_commit_hash: Optional[str] = None, inference_job_id: Optional[int] = None): 
        self.repository_id = repository_id
        self.git_url = git_url
        self.repo_local_path = repo_local_path
        self.task_instance = task_instance
        self.warnings = []
        self.repo_object = None
        self.raw_commit_guru_data = []
        self.commit_hash_to_db_id_map = {}
        self.commit_fix_keyword_map = {}
        self.bug_link_map_hash = {}
        self.raw_ck_metrics = {}
        self.inserted_guru_metrics_count = 0
        self.inserted_ck_metrics_count = 0
        self.parent_commit_hash = None
        self.parent_metrics_processed = False


class IngestionStep(ABC):
    """Abstract base class for an ingestion pipeline step."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Returns the user-friendly name of the step."""
        pass

    @abstractmethod
    def execute(self, context: IngestionContext) -> IngestionContext:
        """
        Executes the logic for this step.

        Args:
            context: The shared IngestionContext object.

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
            # Avoid direct import at top level if task_utils depends on celery potentially
            from shared.utils.task_utils import update_task_state
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