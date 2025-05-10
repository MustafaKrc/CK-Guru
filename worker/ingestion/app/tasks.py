# worker/ingestion/app/tasks.py
import logging
from pathlib import Path

from celery import shared_task, Task
from celery.exceptions import Ignore, Terminated, Reject


from shared.core.config import settings
from shared.db_session import SyncSessionLocal
from shared.db.models import InferenceJob 
from shared.exceptions import InternalError, build_failure_meta
from shared.schemas.enums import JobStatusEnum
from .main import celery_app

# --- Import Pipeline Structures ---
from services.steps.base import IngestionContext # Keep context
from services.strategies import FullHistoryIngestionStrategy, SingleCommitFeatureExtractionStrategy
from services.pipeline import PipelineRunner
from services.dependencies import StepRegistry, DependencyProvider


from celery.utils.log import get_task_logger

# Use Celery's logger for tasks
logger = get_task_logger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


# --- Feature Extraction Task ---
@shared_task(bind=True, name='tasks.ingest_features_for_inference', acks_late=True)
def ingest_features_for_inference_task(self: Task, inference_job_id: int, repo_id: int, commit_hash_input: str):
    """
    Celery task to orchestrate feature extraction for a single commit inference
    using the PipelineRunner and SingleCommitFeatureExtractionStrategy.
    """
    task_id = self.request.id
    logger.info(f"Task {task_id}: INIT Feature Extraction for InferenceJob {inference_job_id} (Repo: {repo_id}, Commit: {commit_hash_input[:7]})")
    self.update_state(state='STARTED', meta={'step': 'Initializing Pipeline'})

    # --- Context Setup ---
    base_storage_path = Path(settings.STORAGE_BASE_PATH)
    repo_local_path = base_storage_path / "clones" / f"repo_{repo_id}"
    context = IngestionContext(
        repository_id=repo_id, repo_local_path=repo_local_path,
        task_instance=self, is_single_commit_mode=True,
        target_commit_hash=commit_hash_input, inference_job_id=inference_job_id,
    )

    # --- Strategy and Dependency Setup ---
    strategy = SingleCommitFeatureExtractionStrategy()
    dependency_provider = DependencyProvider(session_factory=SyncSessionLocal)
    step_registry = StepRegistry()
    runner = PipelineRunner(strategy, step_registry, dependency_provider)
    job_status_updater = dependency_provider.job_status_updater

    try:
        # --- Update Job Status to RUNNING ---
        if not job_status_updater.update_job_start(inference_job_id, InferenceJob, task_id):
            # If initial update fails, reject the task permanently
            raise Reject("Initial DB update to RUNNING failed", requeue=False)

        # --- Execute the Pipeline ---
        logger.info(f"Task {task_id}: === Executing Feature Extraction Pipeline ===")
        final_context = runner.run(context)
        logger.info(f"Task {task_id}: === Feature Extraction Pipeline Finished ===")

        # --- Dispatch Prediction Task (on success) ---
        self.update_state(state='RUNNING', meta={'step': 'Dispatching Prediction', 'progress': 95}) # Use RUNNING state
        task_name = "tasks.inference_predict"
        args = [inference_job_id] # Pass only job ID
        prediction_task = celery_app.send_task(task_name, args=args, queue="ml_queue")

        if not prediction_task or not prediction_task.id:
            # If dispatch fails *after* pipeline success, it's tricky.
            # Log critical error. The InferenceJob remains RUNNING in DB.
            # Manual intervention or monitoring needed.
            # Mark this Celery task as failed, but don't change DB job status here.
            error_msg = "Feature extraction pipeline succeeded, but failed to dispatch prediction task."
            logger.critical(f"Task {task_id}: {error_msg}")
            self.update_state(state=JobStatusEnum.FAILED, meta=build_failure_meta(InternalError(error_msg)))
            # Don't raise Reject here, as the feature extraction *did* complete.
            # Let the Celery task state reflect the dispatch failure.
            return {"status": "FAILURE", "error": error_msg} # Return error info

        # --- Finalize Task (Success) ---
        success_message = f"Feature extraction complete. Prediction task dispatched: {prediction_task.id}"
        # Note: InferenceJob status remains RUNNING; ML worker updates it upon prediction completion.
        self.update_state(state=JobStatusEnum.SUCCESS, meta={'step': 'Completed', 'progress': 100, 'message': success_message})
        logger.info(f"Task {task_id}: {success_message}")
        return {"status": "SUCCESS", "prediction_task_id": prediction_task.id}

    except Terminated as e:
        # Handle termination signal cleanly
        logger.warning(f"Task {task_id}: Terminated during feature extraction pipeline for job {inference_job_id}")
        status_message = "Task terminated during feature extraction."
        # Update final job status to FAILED
        job_status_updater.update_job_completion(inference_job_id, InferenceJob, JobStatusEnum.FAILED, status_message)
        # Celery handles the REVOKED state update automatically if revoke(terminate=True) was used
        # We log it, update DB, but don't need to explicitly set REVOKED state here.
        raise # Re-raise for Celery to handle

    except (Ignore, Reject) as e:
         # Handle specific Celery control flow exceptions
         logger.info(f"Task {task_id}: Ignoring or Rejecting task for job {inference_job_id}: {e}")
         # Assume DB status was handled before Ignore/Reject was raised if necessary
         raise # Re-raise for Celery

    except Exception as e:
        # Catch all other exceptions from the PipelineRunner
        pipeline_failed_step = getattr(runner.current_step_instance, 'name', 'Unknown')
        error_msg_detail = f"Feature extraction failed at step [{pipeline_failed_step}]: {type(e).__name__}: {str(e)[:200]}"
        logger.critical(f"Task {task_id}: Pipeline Error for job {inference_job_id}. {error_msg_detail}", exc_info=True)

        # Update final job status to FAILED using the service
        job_status_updater.update_job_completion(inference_job_id, InferenceJob, JobStatusEnum.FAILED, error_msg_detail)

        # Update Celery task state to FAILURE
        self.update_state(state=JobStatusEnum.FAILED, meta=build_failure_meta(e, {'failed_step': pipeline_failed_step}))

        # Raise Reject to prevent retries unless explicitly configured
        raise Reject(error_msg_detail, requeue=False) from e


# --- Simplified Full Ingestion Task ---
@shared_task(bind=True, name='tasks.ingest_repository', acks_late=True)
def ingest_repository_task(self: Task, repository_id: int, git_url: str):
    """
    Celery task to orchestrate the full repository ingestion pipeline
    using the PipelineRunner and FullHistoryIngestionStrategy.
    """
    task_id = self.request.id
    logger.info(f"Task {task_id}: INIT Full Ingestion for repo ID: {repository_id}, URL: {git_url}")
    self.update_state(state='STARTED', meta={'step': 'Initializing Pipeline'})

    # --- Context Setup ---
    base_storage_path = Path(settings.STORAGE_BASE_PATH)
    repo_local_path = base_storage_path / "clones" / f"repo_{repository_id}"
    try:
        repo_local_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        # If directory creation fails, reject the task
        error_msg = f'Failed to create storage directory: {e}'
        logger.critical(f"Task {task_id}: {error_msg}", exc_info=True)
        self.update_state(state=JobStatusEnum.FAILED, meta=build_failure_meta(e))
        raise Reject(error_msg, requeue=False) from e

    context = IngestionContext(
        repository_id=repository_id, git_url=git_url, repo_local_path=repo_local_path,
        task_instance=self, is_single_commit_mode=False,
    )

    # --- Strategy and Dependency Setup ---
    strategy = FullHistoryIngestionStrategy()
    dependency_provider = DependencyProvider(session_factory=SyncSessionLocal)
    step_registry = StepRegistry()
    runner = PipelineRunner(strategy, step_registry, dependency_provider)

    try:
        # --- Execute the Pipeline ---
        logger.info(f"Task {task_id}: === Executing Full Ingestion Pipeline ===")
        final_context = runner.run(context)
        logger.info(f"Task {task_id}: === Full Ingestion Pipeline Finished ===")

        # --- Finalize Task (Success) ---
        final_status_message = "Completed successfully"
        if final_context.warnings:
             final_status_message = "Completed with warnings"
             logger.warning(f"Task {task_id}: Full ingestion completed with warnings: {final_context.warnings}")

        # Prepare result payload based on final context state
        result_payload = {
            'status': final_status_message,
            'repository_id': final_context.repository_id,
            'commit_guru_metrics_processed': len(final_context.raw_commit_guru_data),
            'commit_guru_metrics_inserted': final_context.inserted_guru_metrics_count,
            'ck_metrics_processed_commits': len(final_context.raw_ck_metrics),
            'ck_metrics_inserted': final_context.inserted_ck_metrics_count,
            'warnings': "; ".join(final_context.warnings) if final_context.warnings else None
        }
        self.update_state(state=JobStatusEnum.SUCCESS, meta=result_payload) # Use payload in meta
        logger.info(f"Task {task_id}: Final State: SUCCESS. {final_status_message}")
        return result_payload

    except Terminated as term_exc:
        # Handle termination signal cleanly
        failed_step_name = getattr(runner.current_step_instance, 'name', 'Unknown')
        error_msg = f"Full ingestion task terminated during step: {failed_step_name}."
        logger.warning(f"Task {task_id}: {error_msg}")
        # Update Celery task state; DB job status isn't applicable here
        self.update_state(state='REVOKED', meta={'exc_type': 'Terminated', 'exc_message': error_msg, 'failed_step': failed_step_name})
        raise # Re-raise for Celery

    except (Ignore, Reject) as e:
         # Handle specific Celery control flow exceptions
         logger.info(f"Task {task_id}: Ignoring or Rejecting task for repo {repository_id}: {e}")
         raise # Re-raise for Celery

    except Exception as e:
        # Catch all other exceptions from the PipelineRunner
        pipeline_failed_step = getattr(runner.current_step_instance, 'name', 'Unknown')
        error_type = type(e).__name__
        error_message = f"Full ingestion pipeline failed at step '{pipeline_failed_step}' due to {error_type}: {str(e)[:500]}" # Truncate
        logger.critical(f"Task {task_id}: Pipeline Error for repo {repository_id}. {error_message}", exc_info=True)

        # Update Celery task state to FAILURE
        self.update_state(state=JobStatusEnum.FAILED, meta=build_failure_meta(e, {'failed_step': pipeline_failed_step}))

        # Raise Reject to prevent retries unless explicitly configured
        raise Reject(error_message, requeue=False) from e
    