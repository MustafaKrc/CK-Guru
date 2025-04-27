# worker/ingestion/app/tasks.py
import logging
from pathlib import Path
from typing import List, Optional, Dict, Tuple
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
from shared.db.models import CommitGuruMetric, CKMetric, InferenceJob
from shared.schemas.enums import JobStatusEnum
from .main import celery_app

# Import steps and context
from services.steps.base import IngestionContext, IngestionStep
from services.steps.link_bugs import LinkBugsStep
from services.steps.prepare_repo import PrepareRepositoryStep
from services.steps.calculate_guru import CalculateCommitGuruMetricsStep
from services.steps.persist_guru_and_link_issues import PersistCommitGuruAndLinkIssuesStep
from services.steps.calculate_ck import CalculateCKMetricsStep
from services.steps.persist_ck import PersistCKMetricsStep
from services import job_db_service as ingestion_job_db_service

from celery.utils.log import get_task_logger

# Use Celery's logger for tasks
logger = get_task_logger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

# --- Helper Function (Keep as is or slightly modify if needed) ---
def _run_calculation_steps_for_commit(
    session: Session,
    context: IngestionContext,
    commit_to_process: str,
    parent_commit_for_diff: Optional[str] = None,
    is_parent_calc: bool = False
) -> bool:
    """Runs Guru and CK calculation and persistence for a specific commit."""
    step_prefix = "Parent" if is_parent_calc else "Target"
    logger.info(f"Running calculation steps for {step_prefix} Commit: {commit_to_process[:7]}")

    # Store original target commit hash from context
    original_target = context.target_commit_hash
    # Set the context's target hash to the commit we want steps to process
    context.target_commit_hash = commit_to_process
    # Store the parent hash needed for diff calculation within the context
    context.parent_commit_hash = parent_commit_for_diff if not is_parent_calc else None # Parent needs its own parent for diff

    success = False
    try:
        # The steps should now use context.target_commit_hash and context.parent_commit_hash
        # Ensure steps like CalculateCommitGuruMetricsStep are modified to accept the parent hash for diffing.
        # TODO: Verify CalculateCommitGuruMetricsStep uses context.parent_commit_hash if available for diff calculation.

        CalculateCommitGuruMetricsStep().execute(context)
        PersistCommitGuruAndLinkIssuesStep().execute(context)
        CalculateCKMetricsStep().execute(context)
        PersistCKMetricsStep().execute(context)

        success = True
        logger.info(f"Successfully processed {step_prefix} Commit: {commit_to_process[:7]}")
    except Exception as e:
        logger.error(f"Failed processing {step_prefix} Commit {commit_to_process[:7]}: {e}", exc_info=True)
        success = False
    finally:
        # Restore original target hash in context
        context.target_commit_hash = original_target
        context.parent_commit_hash = None # Clear parent hash specific to this run

    return success


# --- Helper Function to Check Metric Existence ---
def _check_metrics_exist(session: Session, repo_id: int, commit_hash: str) -> bool:
    """Checks if both CommitGuru and CK metrics exist for a commit."""
    cgm_exists_query = select(CommitGuruMetric.id).where(
        CommitGuruMetric.repository_id == repo_id,
        CommitGuruMetric.commit_hash == commit_hash
    ).limit(1).exists()
    cgm_exists = session.execute(select(cgm_exists_query)).scalar()

    ckm_exists_query = select(CKMetric.id).where(
        CKMetric.repository_id == repo_id,
        CKMetric.commit_hash == commit_hash
    ).limit(1).exists()
    ckm_exists = session.execute(select(ckm_exists_query)).scalar()

    return cgm_exists and ckm_exists

# --- Modified Task ---
@shared_task(bind=True, name='tasks.ingest_specific_commit', acks_late=True)
def ingest_specific_commit_task(self: Task, repo_id: int, target_commit_hash_input: str, inference_job_id: int):
    task_id = self.request.id
    logger.info(f"Task {task_id}: Starting feature extraction for InferenceJob {inference_job_id} (Repo: {repo_id}, Commit: {target_commit_hash_input[:7]})")

    base_storage_path = Path(settings.STORAGE_BASE_PATH)
    repo_local_path = base_storage_path / "clones" / f"repo_{repo_id}"

    # Use target_commit_hash_input initially, might be updated to full hash
    context = IngestionContext(
        repository_id=repo_id,
        git_url="",
        repo_local_path=repo_local_path,
        task_instance=self,
        target_commit_hash=target_commit_hash_input, # Use input initially
        inference_job_id=inference_job_id
    )

    parent_hash: Optional[str] = None
    parent_metrics_ok = False
    target_metrics_exist = False # Flag for target metrics
    final_status = JobStatusEnum.FAILED

    try:
        update_task_state(self, 'STARTED', 'Initializing feature extraction...', 0)

        with get_sync_db_session() as session:
            try:
                ingestion_job_db_service.update_inference_job_status(
                    session, inference_job_id, JobStatusEnum.RUNNING,
                    f"Feature extraction started (Task: {task_id})", task_id, is_start=True
                )
                session.commit()

                prepare_step = PrepareRepositoryStep()
                context = prepare_step.execute(context)
                if not context.repo_object: raise RuntimeError("Failed to prepare repository object.")
                update_task_state(self, 'STARTED', 'Repository prepared.', 10)

                # --- Resolve Full Hash ---
                try:
                    target_commit_full_hash = context.repo_object.commit(target_commit_hash_input).hexsha
                    if target_commit_full_hash != target_commit_hash_input:
                        logger.info(f"Resolved short hash {target_commit_hash_input[:7]} to {target_commit_full_hash[:7]}")
                    context.target_commit_hash = target_commit_full_hash # Update context with full hash
                except (git.BadName, ValueError) as e:
                    raise ValueError(f"Invalid target commit hash '{target_commit_hash_input}': {e}") from e

                # --- Parent Commit Check & Processing ---
                update_task_state(self, 'STARTED', 'Checking parent commit...', 20)
                target_commit_obj = context.repo_object.commit(context.target_commit_hash) # Use full hash from context
                if not target_commit_obj.parents:
                    raise ValueError(f"Commit {context.target_commit_hash[:7]} is the initial commit, cannot calculate features requiring a parent.")

                parent_commit = target_commit_obj.parents[0]
                parent_hash = parent_commit.hexsha
                context.parent_commit_hash = parent_hash # Store parent hash in context if needed by steps
                logger.info(f"Identified parent commit: {parent_hash[:7]}")

                # Check DB for parent metrics
                if _check_metrics_exist(session, repo_id, parent_hash):
                    logger.info(f"Parent commit {parent_hash[:7]} metrics found in DB.")
                    parent_metrics_ok = True
                    context.parent_metrics_processed = True
                    update_task_state(self, 'STARTED', 'Parent metrics found.', 30)
                else:
                    logger.warning(f"Parent commit {parent_hash[:7]} metrics NOT found in DB. Attempting calculation...")
                    update_task_state(self, 'STARTED', 'Calculating parent metrics...', 30)
                    # Determine grandparent hash for parent diff calculation
                    grandparent_hash = parent_commit.parents[0].hexsha if parent_commit.parents else None
                    success = _run_calculation_steps_for_commit(
                        session=session, context=context, commit_to_process=parent_hash,
                        parent_commit_for_diff=grandparent_hash, is_parent_calc=True
                    )
                    if success:
                        parent_metrics_ok = True
                        context.parent_metrics_processed = True
                        logger.info(f"Successfully calculated and persisted parent metrics for {parent_hash[:7]}.")
                        session.commit() # Commit parent metrics
                        update_task_state(self, 'STARTED', 'Parent metrics calculated.', 60)
                    else:
                        raise RuntimeError(f"Failed to calculate required metrics for parent commit {parent_hash[:7]}.")

                # --- Target Commit Check & Processing ---
                if parent_metrics_ok:
                    update_task_state(self, 'STARTED', f'Checking target commit {context.target_commit_hash[:7]} metrics...', 65)
                    # Check DB for *target* metrics before calculating
                    if _check_metrics_exist(session, repo_id, context.target_commit_hash):
                        logger.info(f"Target commit {context.target_commit_hash[:7]} metrics ALREADY exist in DB. Skipping calculation.")
                        target_metrics_exist = True # Mark as existing
                        update_task_state(self, 'STARTED', 'Target metrics found.', 90) # Skip to near end
                    else:
                        logger.info(f"Target commit {context.target_commit_hash[:7]} metrics not found. Calculating...")
                        update_task_state(self, 'STARTED', f'Calculating target commit {context.target_commit_hash[:7]} metrics...', 70)
                        # Calculate target metrics (using parent hash for diff)
                        success = _run_calculation_steps_for_commit(
                            session=session, context=context, commit_to_process=context.target_commit_hash,
                            parent_commit_for_diff=parent_hash, is_parent_calc=False
                        )
                        if not success:
                            raise RuntimeError(f"Failed to calculate metrics for target commit {context.target_commit_hash[:7]}.")

                        session.commit() # Commit target metrics
                        target_metrics_exist = True # Mark as calculated
                        update_task_state(self, 'STARTED', 'Target metrics calculated.', 90)
                        logger.info(f"Successfully calculated and persisted target metrics for {context.target_commit_hash[:7]}.")

                    # --- Dispatch Inference Task (if target metrics ready) ---
                    if target_metrics_exist:
                        ml_task_name = 'tasks.inference' # CORRECTED task name
                        ml_queue = 'ml_queue'
                        try:
                            logger.info(f"Dispatching ML inference task ({ml_task_name}) for InferenceJob {inference_job_id}...")
                            celery_app.send_task(
                                ml_task_name,
                                args=[inference_job_id],
                                queue=ml_queue
                            )
                            logger.info(f"ML inference task dispatched successfully to queue '{ml_queue}'.")
                            final_status = JobStatusEnum.SUCCESS
                            status_message = "Feature extraction complete (or features found). Inference task dispatched."
                            update_task_state(self, 'SUCCESS', status_message, 100)
                        except Exception as dispatch_err:
                            logger.error(f"Failed to dispatch ML inference task: {dispatch_err}", exc_info=True)
                            raise RuntimeError("Failed to dispatch inference task after feature extraction.") from dispatch_err
                    else:
                        # This case shouldn't be reachable if logic is correct
                         raise RuntimeError("Target metrics processing failed unexpectedly.")
                else:
                    # This path shouldn't be reached if parent calc fails due to raise
                     raise RuntimeError("Parent metrics processing failed unexpectedly.")

            # --- Error Handling within Session ---
            except (SQLAlchemyError, git.GitCommandError, ValueError, RuntimeError, Exception) as e:
                session.rollback()
                error_msg = f"Failed feature extraction for {context.target_commit_hash[:7]}: {type(e).__name__}: {e}"
                logger.error(error_msg, exc_info=True)
                try:
                    ingestion_job_db_service.update_inference_job_status(
                        session, inference_job_id, JobStatusEnum.FAILED, error_msg, task_id
                    )
                    session.commit()
                except Exception as db_fail_err:
                     logger.error(f"CRITICAL - Failed to update InferenceJob {inference_job_id} status to FAILED in DB: {db_fail_err}", exc_info=True)
                     session.rollback()
                update_task_state(self, 'FAILURE', error_msg, 0)
                # Use Reject because these are generally non-transient errors
                raise Reject(error_msg, requeue=False) from e

    # --- Outer Error Handling ---
    except Terminated:
        logger.warning(f"Task {task_id} terminated during feature extraction for InferenceJob {inference_job_id}.")
        final_status = JobStatusEnum.FAILED # Mark FAILED on revoke
        status_message = "Task terminated by request during feature extraction."
        try:
            with get_sync_db_session() as final_session:
                ingestion_job_db_service.update_inference_job_status(
                    final_session, inference_job_id, final_status, status_message, task_id
                )
                final_session.commit()
        except Exception as db_term_err:
            logger.error(f"Failed to update DB status after task termination: {db_term_err}", exc_info=True)
        raise # Re-raise Terminated

    except Reject:
        raise # Re-raise Reject exceptions

    except Exception as outer_e:
        status_message = f"Unexpected error in ingest_specific_commit_task: {type(outer_e).__name__}"
        logger.critical(f"Task {task_id}: {status_message}", exc_info=True)
        final_status = JobStatusEnum.FAILED
        try:
            with get_sync_db_session() as final_session:
                ingestion_job_db_service.update_inference_job_status(
                    final_session, inference_job_id, final_status, status_message, task_id
                )
                final_session.commit()
        except Exception as db_outer_err:
            logger.error(f"Failed to update DB status after outer task error: {db_outer_err}", exc_info=True)
        update_task_state(self, 'FAILURE', status_message, 0)
        raise Reject(status_message, requeue=False) from outer_e

    if final_status == JobStatusEnum.SUCCESS:
        return {"status": "SUCCESS", "message": status_message, "inference_job_id": inference_job_id}
    else:
        raise RuntimeError("Task finished unexpectedly without success or explicit error.")

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
