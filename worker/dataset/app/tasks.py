# worker/dataset/app/tasks.py
import logging
import traceback
from typing import Optional # Import traceback

import s3fs
from celery import shared_task, Task
from celery.exceptions import Ignore, Terminated, Reject # Import Reject

# --- Remove old generator import ---
# from services.dataset_generator import DatasetGenerator

# --- Import New Pipeline Structures ---
from services.context import DatasetContext
from services.dependencies import DependencyProvider, StepRegistry
from services.strategies import DefaultDatasetGenerationStrategy # Import default strategy
from services.pipeline import PipelineRunner

# --- Import Config, Session, Enums, Status Updater Interface ---
from shared.core.config import settings
from shared.db_session import get_sync_db_session, SyncSessionLocal # Import factory
from shared.schemas.enums import DatasetStatusEnum
from shared.services.interfaces import IJobStatusUpdater # For type hint if needed

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

@shared_task(bind=True, name='tasks.generate_dataset', acks_late=True) # Enable acks_late
def generate_dataset_task(self: Task, dataset_id: int):
    """
    Celery task to generate a dataset using the PipelineRunner.
    """
    task_id = self.request.id
    logger.info(f"Celery Task {task_id}: INIT Dataset Generation for ID {dataset_id}")
    self.update_state(state='STARTED', meta={'step': 'Initializing Pipeline'})

    # --- Instantiate Pipeline Components ---
    dependency_provider: Optional[DependencyProvider] = None # Initialize for finally block
    job_status_updater: Optional[IJobStatusUpdater] = None

    try:
        # Pass the synchronous session factory
        dependency_provider = DependencyProvider(session_factory=SyncSessionLocal)
        step_registry = StepRegistry()
        strategy = DefaultDatasetGenerationStrategy()
        runner = PipelineRunner(strategy, step_registry, dependency_provider)
        job_status_updater = dependency_provider._get_job_status_updater() # Get updater for error handling

        # --- Create Initial Context ---
        initial_context = DatasetContext(
            dataset_id=dataset_id,
            task_instance=self,
            # Other fields will be populated by LoadConfigurationStep
        )

        # --- Execute Pipeline ---
        logger.info(f"Task {task_id}: === Executing Dataset Generation Pipeline ===")
        final_context = runner.run(initial_context)
        logger.info(f"Task {task_id}: === Dataset Generation Pipeline Finished ===")

        # --- Finalize Task (Success) ---
        # DB status is updated by WriteOutputStep via JobStatusUpdater
        # Celery status updated by PipelineRunner/WriteOutputStep
        success_message = f"Dataset generation complete. Rows written: {final_context.rows_written}."
        # Update Celery state one last time to ensure SUCCESS state and final message
        self.update_state(state='SUCCESS', meta={'progress': 100, 'step': 'Completed', 'message': success_message, 'path': final_context.output_storage_uri})
        logger.info(f"Task {task_id}: Final State: SUCCESS. {success_message}")
        return { # Return final status payload
            'dataset_id': final_context.dataset_id,
            'status': 'SUCCESS',
            'rows_written': final_context.rows_written,
            'path': final_context.output_storage_uri,
            'background_path': final_context.background_sample_uri,
            'warnings': final_context.warnings
        }

    except Terminated as e:
        # Handle termination signal cleanly
        logger.warning(f"Task {task_id}: Terminated during dataset generation pipeline for dataset {dataset_id}.")
        if job_status_updater:
             # Attempt to update DB status to FAILED
             status_message = "Task terminated by revoke request."
             job_status_updater.update_dataset_completion(dataset_id, DatasetStatusEnum.FAILED, status_message)
        else:
             logger.error("JobStatusUpdater not available during termination handling.")
        # Celery handles the REVOKED state update automatically
        raise # Re-raise for Celery

    except (Ignore, Reject) as e:
         # Handle specific Celery control flow exceptions
         logger.info(f"Task {task_id}: Ignoring or Rejecting task for dataset {dataset_id}: {e}")
         # Assume DB status was handled before Ignore/Reject was raised if necessary
         raise # Re-raise for Celery

    except Exception as e:
        # Catch all other exceptions from the PipelineRunner or setup
        failed_step = "Initialization"
        if runner and runner.current_step_instance:
             failed_step = runner.current_step_instance.name

        error_msg_detail = f"Dataset generation failed at step [{failed_step}]: {type(e).__name__}: {str(e)}"
        logger.critical(f"Task {task_id}: Pipeline Error for dataset {dataset_id}. {error_msg_detail}", exc_info=True)

        # Update final job status to FAILED using the service
        if job_status_updater:
             job_status_updater.update_dataset_completion(dataset_id, DatasetStatusEnum.FAILED, error_msg_detail[:1000]) # Truncate
        else:
            logger.error(f"Task {task_id}: JobStatusUpdater not available to mark dataset {dataset_id} as FAILED in DB.")

        # Update Celery task state to FAILURE
        self.update_state(state='FAILURE', meta={
            'exc_type': type(e).__name__,
            'exc_message': traceback.format_exc(), # Include traceback in meta
            'failed_step': failed_step
        })

        # Raise Reject to prevent retries unless explicitly configured
        raise Reject(error_msg_detail, requeue=False) from e
    finally:
        # Clean up resources if necessary (though session scope handles DB)
        logger.debug(f"Task {task_id}: Finalizing dataset generation task.")
        # dependency_provider might have resources to release if it managed them directly

# --- Keep delete task as is ---
@shared_task(
    bind=True,
    name='tasks.delete_storage_object',
    autoretry_for=(ConnectionError, TimeoutError), # Example retryable errors
    retry_kwargs={'max_retries': 3, 'countdown': 60}
)
def delete_storage_object_task(self: Task, object_storage_uri: str):
    """Deletes an object from S3/MinIO storage."""
    task_id = self.request.id
    logger.info(f"Task {task_id}: Received request to delete object: {object_storage_uri}")

    if not object_storage_uri or not object_storage_uri.startswith("s3://"):
        logger.warning(f"Task {task_id}: Invalid or missing object storage URI: '{object_storage_uri}'. Ignoring.")
        raise Ignore()

    try:
        storage_options = settings.s3_storage_options
        fs = s3fs.S3FileSystem(**storage_options)
        s3_path = object_storage_uri.replace("s3://", "")

        if fs.exists(s3_path):
            logger.info(f"Task {task_id}: Object found. Deleting {object_storage_uri}...")
            fs.rm(s3_path)
            logger.info(f"Task {task_id}: Successfully deleted object: {object_storage_uri}")
            return {"status": "deleted", "uri": object_storage_uri}
        else:
            logger.warning(f"Task {task_id}: Object not found at {object_storage_uri}, no deletion performed.")
            return {"status": "not_found", "uri": object_storage_uri}

    except FileNotFoundError:
        logger.warning(f"Task {task_id}: Object or path not found for deletion: {object_storage_uri}.")
        raise Ignore()
    except s3fs.errors.S3PermissionError as e:
         logger.error(f"Task {task_id}: Permission error deleting {object_storage_uri}: {e}")
         raise Ignore() # Don't retry permission errors usually
    except Exception as e:
        logger.error(f"Task {task_id}: Failed to delete object {object_storage_uri}: {e}", exc_info=True)
        # Let retry logic handle this based on autoretry_for
        raise e # Re-raise other errors for Celery retry/failure handling