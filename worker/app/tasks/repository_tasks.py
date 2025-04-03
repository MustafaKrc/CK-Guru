# worker/app/tasks/repository_tasks.py
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional, Set

import git
from celery import shared_task, Task # Import Task for type hinting self
from celery.utils.log import get_task_logger
from sqlalchemy.exc import SQLAlchemyError

from ..core.config import settings
from .data_processing.feature_extraction import calculate_and_save_guru_metrics, run_ck_analysis
from .utils.task_utils import update_task_state
from .data_processing.feature_extraction import prepare_repository

logger = get_task_logger(__name__)


# === Main Celery Task (Orchestrator) ===
@shared_task(bind=True, name='tasks.create_repository_dataset')
def create_repository_dataset_task(self: Task, repository_id: int, git_url: str):
    """
    Orchestrates the data extraction process for a repository:
    1. Prepare local clone.
    2. Calculate Commit Guru metrics & link bugs.
    3. Save Commit Guru metrics.
    4. Run CK analysis on recent commits.
    """
    task_id = self.request.id
    logger.info(f"Task {task_id}: Starting data extraction for repo ID: {repository_id}, URL: {git_url}")

    base_storage_path = Path(settings.STORAGE_BASE_PATH)
    repo_local_path = base_storage_path / "clones" / f"repo_{repository_id}"
    repo_local_path.parent.mkdir(parents=True, exist_ok=True)

    repo: Optional[git.Repo] = None
    commit_guru_data_list: List[Dict[str, Any]] = []
    bug_link_map: Dict[str, List[str]] = {}
    total_guru_metrics_inserted = 0
    total_ck_metrics_inserted = 0
    final_status = "Completed successfully"
    warning_info: Optional[str] = None

    try:
        # --- Phase 1: Prepare Repository ---
        update_task_state(self, 'STARTED', 'Preparing repository...', 5)
        repo = prepare_repository(task_id, git_url, repo_local_path)
        update_task_state(self, 'STARTED', 'Repository ready.', 15)

        # --- Phase 2, 3, 4: Calculate, Link, Fetch Issues, Save Commit Guru Metrics ---
        total_guru_metrics_inserted, commit_guru_data_list, guru_warning = calculate_and_save_guru_metrics(
            self, task_id, repository_id, repo_local_path, git_url # Pass git_url
        )
        if guru_warning and not warning_info: # Capture warning if not already set
             warning_info = guru_warning
             final_status = "Completed with warnings"

        # --- Phase 5: Run CK Analysis ---
        if repo: # Ensure repo object is valid before CK
             total_ck_metrics_inserted = run_ck_analysis(
                 self, repository_id, repo, repo_local_path
             )
             # Check if CK phase added a warning
             current_meta = self.AsyncResult(self.request.id).info or {}
             if 'warning' in current_meta and not warning_info: # Avoid overwriting previous warning
                  warning_info = current_meta['warning']
                  final_status = "Completed with warnings (CK analysis issue)"
        else:
             logger.error(f"Task {task_id}: Skipping CK analysis because repository object is invalid.")
             final_status = "Completed with errors (Repo prep failed)" # Upgrade status


        # --- Final Update ---
        update_task_state(self, 'STARTED', 'Finalizing...', 99) # Progress before final SUCCESS state

        result_payload = {
            'status': final_status,
            'repository_id': repository_id,
            'commit_guru_metrics_inserted': total_guru_metrics_inserted,
            'ck_metrics_inserted': total_ck_metrics_inserted,
            'total_commits_analyzed_guru': len(commit_guru_data_list),
        }
        if warning_info:
            result_payload['warning'] = warning_info

        logger.info(f"Task {task_id}: Data extraction finished for repo ID: {repository_id}. Status: {final_status}")
        # Note: Celery automatically sets state to SUCCESS on successful return
        # self.update_state(state='SUCCESS', meta=result_payload) # Explicit SUCCESS state
        return result_payload

    except (git.GitCommandError, SQLAlchemyError, ValueError, Exception) as e:
        # Catch exceptions from helpers or main flow
        error_type = type(e).__name__
        error_message = f"Task failed due to {error_type}: {str(e)}"
        # Log critical for major failures
        if isinstance(e, (git.GitCommandError, SQLAlchemyError)):
             logger.critical(f"Task {task_id}: {error_message}", exc_info=True)
        else:
             logger.error(f"Task {task_id}: {error_message}", exc_info=True)

        # Update state to FAILURE
        try:
            # Check if self exists and has update_state method
             if hasattr(self, 'update_state') and callable(self.update_state):
                  self.update_state(state='FAILURE', meta={'status': 'Task failed', 'error': error_message, 'progress': 0})
        except Exception as update_err:
             logger.error(f"Task {task_id}: Failed to update task state to FAILURE: {update_err}")

        # Important: Re-raise the exception so Celery knows the task failed
        raise e