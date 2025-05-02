# worker/ingestion/app/tasks.py
import logging
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Any
import traceback

from celery import shared_task, Task
from celery.exceptions import Ignore, Terminated, Reject
import git
from sqlalchemy import select, exists # Import exists
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from shared.core.config import settings
from shared.utils.task_utils import update_task_state
from shared.db_session import get_sync_db_session
# Import specific models needed for checks
from shared.db.models import InferenceJob
from shared.schemas.enums import JobStatusEnum
from .main import celery_app # Import app to send tasks

# Import steps and context
from services.steps.base import IngestionContext, IngestionStep
from services.steps.prepare_repo import PrepareRepositoryStep
from services.steps.calculate_guru import CalculateCommitGuruMetricsStep
from services.steps.calculate_ck import CalculateCKMetricsStep
from services.steps.resolve_commit_hashes import ResolveCommitHashesStep
from services.steps.ensure_commits_exist import EnsureCommitsExistLocallyStep
from services.steps.combine_features import CombineFeaturesStep
from services.steps.persist_guru_and_link_issues import PersistCommitGuruAndLinkIssuesStep
from services.steps.link_bugs import LinkBugsStep
from services.steps.persist_ck import PersistCKMetricsStep

from shared.db_utils.job_status_utils import update_job_start_sync, update_job_status_sync, update_inference_job_feature_path_sync

from celery.utils.log import get_task_logger

# Use Celery's logger for tasks
logger = get_task_logger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


# --- New Task for Feature Extraction ---
@shared_task(bind=True, name='tasks.ingest_features_for_inference', acks_late=True)
def ingest_features_for_inference_task(self: Task, inference_job_id: int, repo_id: int, commit_hash_input: str):
    """
    Extracts features for a single commit using adapted ingestion steps,
    then dispatches the prediction task to the ML worker.
    """
    task_id = self.request.id
    logger.info(f"Task {task_id}: Starting feature extraction for InferenceJob {inference_job_id} (Repo: {repo_id}, CommitInput: {commit_hash_input[:7]})")

    self.update_state(state='STARTED', meta={'step': 'Initializing'})

    base_storage_path = Path(settings.STORAGE_BASE_PATH)
    repo_local_path = base_storage_path / "clones" / f"repo_{repo_id}"

    context = IngestionContext(
        repository_id=repo_id,
        git_url="", # URL might not be needed if repo already exists
        repo_local_path=repo_local_path,
        task_instance=self,
        is_single_commit_mode=True, # Crucial flag
        target_commit_hash=commit_hash_input, # Start with input hash
        parent_commit_hash=None, # Will be resolved
        inference_job_id=inference_job_id,
        final_combined_features=None # Initialize combined features holder
    )

    pipeline: List[IngestionStep] = [
        PrepareRepositoryStep(),
        ResolveCommitHashesStep(),
        EnsureCommitsExistLocallyStep(),
        CalculateCommitGuruMetricsStep(),   # Calculates for target/parent
        PersistCommitGuruAndLinkIssuesStep(),# Persists target/parent Guru, links issues
        CalculateCKMetricsStep(),           # Calculates for target/parent
        PersistCKMetricsStep()              # Persists target/parent CK
    ]
    total_steps = len(pipeline)

    # --- Update DB Job Status to RUNNING using SHARED util ---
    try:
        update_job_start_sync(inference_job_id, "inference", task_id)
    except Exception as db_err:
        # Log error, decide if task should fail immediately
        logger.error(f"Task {task_id}: Failed initial DB status update via shared util: {db_err}", exc_info=True)
        self.update_state(state='FAILURE', meta={'exc_type': type(db_err).__name__, 'exc_message': f'DB update failed: {db_err}'})
        raise Reject("Initial DB update failed", requeue=False) from db_err

    final_status = JobStatusEnum.FAILED # Default

    try:
        # Execute pipeline steps sequentially
        for i, step in enumerate(pipeline):
            step_name = step.name
            progress = int(90 * (i / total_steps)) # Allocate 90% for steps
            logger.info(f"Task {task_id}: Running step {i+1}/{total_steps}: {step_name}")
            self.update_state(state='STARTED', meta={'step': step_name, 'progress': progress})
            context = step.execute(context) # Adapt steps for single_commit_mode

        # feature combination is not processed here anymore
        # # Extract final features calculated by CombineFeaturesStep
        # final_features_dict: Optional[Dict[str, Any]] = getattr(context, 'final_combined_features', None)
        # if not final_features_dict:
        #     raise RuntimeError("Feature combination step did not produce features.")

        # --- Dispatch Prediction Task to ML Worker ---
        self.update_state(state='STARTED', meta={'step': 'Dispatching Prediction', 'progress': 95})
        task_name = "tasks.inference_predict" # Task in ML worker
        args = [inference_job_id] # Pass features directly
        prediction_task = celery_app.send_task(task_name, args=args, queue="ml_queue") # Use own celery_app instance to send

        if not prediction_task or not prediction_task.id:
            raise RuntimeError("Failed to dispatch prediction task (invalid task object returned).")

        # --- Update Inference Job Status to PENDING (handled by ML worker) ---
        # No status update needed here, ML worker handles transitions
        message = f"Feature extraction complete. Prediction task dispatched: {prediction_task.id}"
        final_status = JobStatusEnum.SUCCESS # Mark this task as successful

        self.update_state(state='SUCCESS', meta={'step': 'Completed', 'progress': 100, 'message': message})
        logger.info(f"Task {task_id}: {message}")
        return {"status": "SUCCESS", "prediction_task_id": prediction_task.id}

    except Terminated as e:
        logger.warning(f"Task {task_id}: Terminated during feature extraction for job {inference_job_id}")
        status_message = "Task terminated during feature extraction."
        final_status = JobStatusEnum.FAILED # Treat termination as failure for the job
        # Update DB using sync helper
        try: update_job_status_sync(inference_job_id, "inference", final_status, status_message)
        except Exception as db_err: logger.error(f"Failed DB update on Terminated: {db_err}")
        raise e # Let Celery handle state

    except (Ignore, Reject) as e: # Handle Ignore/Reject explicitly
         logger.info(f"Task {task_id}: Ignoring or Rejecting task for job {inference_job_id}: {e}")
         # DB status likely handled by the code raising Ignore/Reject, or needs check
         raise e # Re-raise for Celery

    except Exception as e:
        logger.critical(f"Task {task_id}: Unhandled error during feature extraction for job {inference_job_id}", exc_info=True)
        error_msg = f"Feature extraction failed: {type(e).__name__}: {e}"
        final_status = JobStatusEnum.FAILED
        # Update DB using sync helper
        try: update_job_status_sync(inference_job_id, "inference", final_status, error_msg)
        except Exception as db_err: logger.error(f"Failed DB update on Exception: {db_err}")
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': error_msg})
        raise Reject(error_msg, requeue=False) from e # Fail permanently

# Note: Adapt steps CalculateCommitGuruMetricsStep, CalculateCKMetricsStep, PrepareRepositoryStep
# to handle the `is_single_commit_mode=False` case (their original behavior).
@shared_task(bind=True, name='tasks.ingest_repository')
def ingest_repository_task(self: Task, repository_id: int, git_url: str):
    """
    Orchestrates the FULL ingestion pipeline using distinct steps.
    (Ensure adapted steps still work correctly in this mode).
    """
    task_id = self.request.id
    logger.info(f"Task {task_id}: Starting FULL ingestion pipeline for repo ID: {repository_id}, URL: {git_url}")
    try:
        self.update_state(state='STARTED', meta={'step': 'Initializing'})
    except Exception as e:
        logger.error(f"Task {task_id}: Failed initial state update: {e}", exc_info=True)

    base_storage_path = Path(settings.STORAGE_BASE_PATH)
    repo_local_path = base_storage_path / "clones" / f"repo_{repository_id}"

    try:
        repo_local_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.critical(f"Task {task_id}: Failed to create base directory {repo_local_path.parent}: {e}", exc_info=True)
        self.update_state(state='FAILURE', meta={'exc_type': 'OSError', 'exc_message': f'Failed to create storage directory: {e}'})
        raise RuntimeError(f"Cannot proceed: Failed to create required directory {repo_local_path.parent}") from e

    context = IngestionContext(
        repository_id=repository_id,
        git_url=git_url,
        repo_local_path=repo_local_path,
        task_instance=self,
        is_single_commit_mode=False, # Explicitly false for full ingestion
        target_commit_hash=None,
        parent_commit_hash=None,
        inference_job_id=None,
        final_combined_features=None
    )

    pipeline: List[IngestionStep] = [
        PrepareRepositoryStep(),             # Clones/fetches repo
        CalculateCommitGuruMetricsStep(),    # Calculates raw Guru metrics for history
        PersistCommitGuruAndLinkIssuesStep(),# Saves Guru metrics, fetches/saves/links GitHub issues
        LinkBugsStep(),                      # Runs GitCommitLinker, updates bug flags in DB
        CalculateCKMetricsStep(),            # Calculates raw CK metrics for commits
        PersistCKMetricsStep()               # Saves CK metrics
    ]

    total_steps = len(pipeline)
    final_status = "Completed successfully"
    failed_step_name = "Initialization"

    try:
        for i, step in enumerate(pipeline):
            step_name = step.name
            failed_step_name = step_name
            progress = int(95 * (i / total_steps))
            logger.info(f"Task {task_id}: === Running Full Ingestion Step {i+1}/{total_steps}: {step_name} ===")
            self.update_state(state='STARTED', meta={'step': step_name, 'progress': progress})
            context = step.execute(context)
            logger.info(f"Task {task_id}: === Completed Full Ingestion Step {i+1}/{total_steps}: {step_name} ===")
            progress_end = int(95 * ((i + 1) / total_steps))
            self.update_state(state='STARTED', meta={'step': f"{step_name} Complete", 'progress': min(progress_end, 98)})

        self.update_state(state='STARTED', meta={'step': 'Finalizing', 'progress': 99})
        if context.warnings: final_status = "Completed with warnings"

        result_payload = {
            'status': final_status, 'repository_id': context.repository_id,
            'commit_guru_metrics_processed': len(context.raw_commit_guru_data),
            'commit_guru_metrics_inserted': context.inserted_guru_metrics_count,
            'ck_metrics_processed_commits': len(context.raw_ck_metrics),
            'ck_metrics_inserted': context.inserted_ck_metrics_count,
            'warnings': "; ".join(context.warnings) if context.warnings else None
        }
        logger.info(f"Task {task_id}: Full ingestion pipeline finished for repo ID: {repository_id}. Final Status: {final_status}")
        self.update_state(state='SUCCESS', meta={'step': 'Complete', 'progress': 100, 'message': final_status})
        return result_payload

    except Terminated as term_exc:
        error_msg = f"Full ingestion task terminated during step: {failed_step_name}."
        logger.warning(f"Task {task_id}: {error_msg}")
        self.update_state(state='REVOKED', meta={'exc_type': 'Terminated', 'exc_message': error_msg})
        raise
    except Exception as e:
        error_type = type(e).__name__
        error_message = f"Full ingestion pipeline failed at step '{failed_step_name}' due to {error_type}: {str(e)}"
        logger.critical(f"Task {task_id}: {error_message}", exc_info=True)
        self.update_state(state='FAILURE', meta={'exc_type': error_type, 'exc_message': error_message, 'failed_step': failed_step_name})
        raise