# worker/dataset/app/tasks.py
import traceback
import logging

import s3fs
from celery import shared_task, Task
from celery.exceptions import Ignore, Terminated

# Import the generator and config/session utils
from services.dataset_generator import DatasetGenerator
from services.cleaning_rules.base import WORKER_RULE_REGISTRY
from shared.core.config import settings
from shared.db_session import get_sync_db_session # Keep for delete task

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

@shared_task(bind=True, name='tasks.generate_dataset')
def generate_dataset_task(self: Task, dataset_id: int):
    """
    Celery task to generate a dataset using the DatasetGenerator.
    """
    task_id = self.request.id
    logger.info(f"Celery Task {task_id}: Received request for dataset ID {dataset_id}")
    
    try:
        generator = DatasetGenerator(dataset_id, self)
        result = generator.generate() # generate() handles internal state updates and cleanup
        logger.info(f"Celery Task {task_id}: generate() finished with result: {result}")
        return result # Return success payload
    except Terminated:
         # Task was revoked, generate() already handled logging/cleanup
         # Celery marks task as REVOKED based on the exception
         logger.warning(f"Celery Task {task_id}: generate() raised Terminated. Task state should be REVOKED.")
         # No return value needed, Celery handles state.
         raise
    except Exception as e:
        # Catch any exception that escaped generate() - should be rare if generate() handles its errors
        error_msg = f"Unhandled exception in generate_dataset_task for dataset {dataset_id}: {type(e).__name__}"
        logger.critical(f"Celery Task {task_id}: {error_msg}", exc_info=True)
        # Ensure Celery backend receives exception type and message
        self.update_state(
            state='FAILURE',
            meta={
                'exc_type': type(e).__name__,
                'exc_message': str(e)
            }
        )
        raise e # Re-raise to let Celery handle the task failure


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
         raise Ignore()
    except Exception as e:
        logger.error(f"Task {task_id}: Failed to delete object {object_storage_uri}: {e}", exc_info=True)
        raise e # Re-raise other errors for Celery retry/failure handling