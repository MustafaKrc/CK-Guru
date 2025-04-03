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
    Orchestrates data extraction: Repo prep, Commit Guru metrics (with GitHub issue cache),
    bug linking, CK analysis.
    """
    task_id = self.request.id
    logger.info(f"Task {task_id}: Starting data extraction for repo ID: {repository_id}, URL: {git_url}")

    base_storage_path = Path(settings.STORAGE_BASE_PATH)
    repo_local_path = base_storage_path / "clones" / f"repo_{repository_id}"
    repo_local_path.parent.mkdir(parents=True, exist_ok=True)

    repo: Optional[git.Repo] = None
    commit_guru_raw_data_list: List[Dict[str, Any]] = [] # Hold raw data for CK phase if needed
    total_guru_metrics_inserted = 0
    total_ck_metrics_inserted = 0
    final_status = "Completed successfully"
    # Collect warnings from different phases
    warnings: List[str] = []

    try:
        # --- Phase 1: Prepare Repository ---
        update_task_state(self, 'STARTED', 'Preparing repository...', 5)
        repo = prepare_repository(git_url, repo_local_path)
        update_task_state(self, 'STARTED', 'Repository ready.', 15)

        # --- Phase 2, 3, 4: Calculate Guru Metrics, Process Issues, Link Bugs, Save ---
        # This function now handles insertion, issue linking, and bug linking updates
        inserted_count, commit_guru_raw_data_list, guru_warning = calculate_and_save_guru_metrics(
            self, repository_id, repo_local_path, git_url
        )
        total_guru_metrics_inserted = inserted_count
        if guru_warning:
            warnings.append(guru_warning)
            final_status = "Completed with warnings"

        # --- Phase 5: Run CK Analysis ---
        update_task_state(self, 'STARTED', 'Starting CK metric extraction...', 90)
        if repo:
            total_ck_metrics_inserted = run_ck_analysis(
                self, repository_id, repo, repo_local_path
            )
            # Check if CK phase added a warning via task meta (if it uses update_task_state with warning)
            # current_meta = self.AsyncResult(self.request.id).info or {} # Requires result backend
            # ck_warning = current_meta.get('warning')
            # This part is less reliable without result backend, rely on logs for CK errors for now.
        else:
            ck_err_msg = f"Task {task_id}: Skipping CK analysis because repository object is invalid."
            logger.error(ck_err_msg)
            warnings.append("CK analysis skipped (Repo prep failed)")
            final_status = "Completed with errors"


        # --- Final Update ---
        update_task_state(self, 'STARTED', 'Finalizing...', 99)

        result_payload = {
            'status': final_status,
            'repository_id': repository_id,
            'commit_guru_metrics_inserted': total_guru_metrics_inserted,
            'ck_metrics_inserted': total_ck_metrics_inserted,
            'total_commits_analyzed_guru': len(commit_guru_raw_data_list), # Based on raw list from guru calc
        }
        if warnings:
            result_payload['warnings'] = "; ".join(warnings)

        logger.info(f"Task {task_id}: Data extraction finished for repo ID: {repository_id}. Status: {final_status}")
        # Celery sets state to SUCCESS on successful return
        return result_payload

    except (git.GitCommandError, SQLAlchemyError, ValueError, Exception) as e:
        error_type = type(e).__name__
        error_message = f"Task failed due to {error_type}: {str(e)}"
        # Log critical for major failures
        if isinstance(e, (git.GitCommandError, SQLAlchemyError)):
             logger.critical(f"Task {task_id}: {error_message}", exc_info=True)
        else:
             logger.error(f"Task {task_id}: {error_message}", exc_info=True)

        try:
            if hasattr(self, 'update_state') and callable(self.update_state):
                  # Define meta structure matching TaskStatusResponse schema
                  meta = {
                      'status': 'Task failed', # Use enum if schema is accessible
                      'error': error_message,
                      'progress': None, # Optional: Reset progress on failure
                      'status_message': 'Task encountered a critical error.'
                  }
                  self.update_state(state='FAILURE', meta=meta)
        except Exception as update_err:
             logger.error(f"Task {task_id}: Failed to update task state to FAILURE: {update_err}")

        raise e # Re-raise the exception