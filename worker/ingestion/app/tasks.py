#  worker/ingestion/app/tasks.py
import logging
from pathlib import Path
from typing import List 

from celery import shared_task, Task
from celery.exceptions import Terminated

from shared.core.config import settings
from shared.utils.task_utils import update_task_state

# Import steps and context
from services.steps.base import IngestionContext, IngestionStep
from services.steps.prepare_repo import PrepareRepositoryStep
from services.steps.calculate_guru import CalculateCommitGuruMetricsStep
from services.steps.persist_guru_and_link_issues import PersistCommitGuruAndLinkIssuesStep
from services.steps.link_bugs import LinkBugsStep
from services.steps.calculate_ck import CalculateCKMetricsStep
from services.steps.persist_ck import PersistCKMetricsStep
# Import the logger setup from Celery for tasks
from celery.utils.log import get_task_logger

# Use Celery's logger for tasks
logger = get_task_logger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


@shared_task(bind=True, name='tasks.ingest_repository')
def ingest_repository_task(self: Task, repository_id: int, git_url: str):
    """
    Orchestrates the refactored ingestion pipeline using distinct steps.
    """
    task_id = self.request.id
    logger.info(f"Task {task_id}: Starting REFACTORED ingestion pipeline for repo ID: {repository_id}, URL: {git_url}")
    # Use update_task_state from the start
    try:
        update_task_state(self, 'STARTED', 'Initializing ingestion pipeline...', 0)
    except Exception as e:
         logger.error(f"Task {task_id}: Failed initial state update: {e}", exc_info=True)
         # Don't fail the whole task just for state update failure

    base_storage_path = Path(settings.STORAGE_BASE_PATH)
    repo_local_path = base_storage_path / "clones" / f"repo_{repository_id}"

    # Ensure parent directory exists
    try:
        repo_local_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.critical(f"Task {task_id}: Failed to create base directory {repo_local_path.parent}: {e}", exc_info=True)
        update_task_state(self, 'FAILURE', f"Failed to create storage directory: {e}", 0)
        # Raise a clear error indicating the problem
        raise RuntimeError(f"Cannot proceed: Failed to create required directory {repo_local_path.parent}") from e

    # Initialize context
    context = IngestionContext(
        repository_id=repository_id,
        git_url=git_url,
        repo_local_path=repo_local_path,
        task_instance=self
    )

    # Define the ingestion pipeline steps
    # Order matters!
    pipeline: List[IngestionStep] = [
        PrepareRepositoryStep(),             # Clones/fetches repo
        CalculateCommitGuruMetricsStep(),    # Calculates raw Guru metrics
        PersistCommitGuruAndLinkIssuesStep(),# Saves Guru metrics, fetches/saves/links GitHub issues
        LinkBugsStep(),                      # Runs GitCommitLinker, updates bug flags in DB
        CalculateCKMetricsStep(),            # Calculates raw CK metrics for commits
        PersistCKMetricsStep()               # Saves CK metrics
        # --- Add new steps here for extensibility ---
        # Example: CalculateCodeComplexityStep(),
    ]

    total_steps = len(pipeline)
    final_status = "Completed successfully"
    current_step_index = -1 # Track current step index for error reporting
    failed_step_name = "Initialization" # Default if fails before loop

    try:
        # Execute the pipeline
        for i, step in enumerate(pipeline):
            current_step_index = i
            step_name = step.name
            failed_step_name = step_name # Keep track of the current step for error reporting

            # Calculate progress allocation for this step
            # Simple linear allocation for now (e.g., 95% total for steps)
            progress_start = int(95 * (i / total_steps))
            progress_end = int(95 * ((i + 1) / total_steps))

            logger.info(f"Task {task_id}: === Executing Step {i+1}/{total_steps}: {step_name} ===")
            update_task_state(self, 'STARTED', f'Step {i+1}/{total_steps}: {step_name}...', progress_start)

            # Execute the step, passing the context
            context = step.execute(context) # Updates context in place or returns updated one

            logger.info(f"Task {task_id}: === Completed Step {i+1}/{total_steps}: {step_name} ===")
            # Update progress slightly less than full end to leave room for final step/wrap-up
            update_task_state(self, 'STARTED', f'Step {i+1}/{total_steps}: {step_name} completed.', min(progress_end, 98))

        # --- Pipeline completed ---
        update_task_state(self, 'STARTED', 'Finalizing...', 99)
        if context.warnings:
             final_status = "Completed with warnings"

        # Construct final result payload from context
        result_payload = {
            'status': final_status,
            'repository_id': context.repository_id,
            'commit_guru_metrics_processed': len(context.raw_commit_guru_data),
            'commit_guru_metrics_inserted': context.inserted_guru_metrics_count,
            'ck_metrics_processed_commits': len(context.raw_ck_metrics), # Commits CK ran for
            'ck_metrics_inserted': context.inserted_ck_metrics_count,
        }
        if context.warnings:
            result_payload['warnings'] = "; ".join(context.warnings)

        logger.info(f"Task {task_id}: Ingestion pipeline finished for repo ID: {repository_id}. Final Status: {final_status}")
        # Update final Celery task state to SUCCESS (done implicitly by returning)
        # If you want explicit success message:
        # update_task_state(self, 'SUCCESS', final_status, 100) # Though return handles this

        return result_payload # Returning dict marks task as SUCCESS

    except Terminated as term_exc:
        # Handle termination gracefully
        error_msg = f"Ingestion task terminated by revoke request during step: {failed_step_name}."
        logger.warning(f"Task {task_id}: {error_msg} (Details: {term_exc})")
        update_task_state(self, 'FAILURE', error_msg, 0) # Mark as failed on revoke
        # include exception info for Celery backend
        self.update_state(
            state='REVOKED',
            meta={'exc_type': type(term_exc).__name__, 'exc_message': str(term_exc)}
        )
        raise

    except Exception as e:
        # Handle pipeline errors
        error_type = type(e).__name__
        error_message = f"Pipeline failed at step '{failed_step_name}' due to {error_type}: {str(e)}"
        logger.critical(f"Task {task_id}: {error_message}", exc_info=True)
        try:
            # Update Celery state with error details
            meta = {'error': error_message, 'failed_step': failed_step_name}
            # Use update_task_state helper
            update_task_state(self, 'FAILURE', f"Failed at step: {failed_step_name}", 0, warning=error_message)
        except Exception as update_err:
            logger.error(f"Task {task_id}: Failed to update task state to FAILURE after critical error: {update_err}")
        # include exception info for Celery backend
        self.update_state(
            state='FAILURE',
            meta={'exc_type': error_type, 'exc_message': str(e)}
        )
        raise
