# worker/ml/app/tasks.py
import logging
from celery import shared_task, Task

# Import Handlers (adjust path if needed)
from services.handlers.training_handler import TrainingJobHandler
from services.handlers.hp_search_handler import HPSearchJobHandler
from services.handlers.inference_handler import InferenceJobHandler
# Import job DB service if needed for direct updates (though handlers should manage)
# from services import job_db_service

logger = logging.getLogger(__name__)

@shared_task(bind=True, name='tasks.train_model')
def train_model_task(self: Task, training_job_id: int):
    """Celery task facade for training jobs."""
    logger.info(f"Task {self.request.id}: Received training request for Job ID {training_job_id}")
    try:
        handler = TrainingJobHandler(training_job_id, self)
        # The handler's run_job method now manages the entire lifecycle,
        # including DB updates and Celery state updates.
        return handler.run_job()
    except Exception as e:
        # Log uncaught exceptions from handler instantiation or run_job setup
        # Note: run_job itself has robust error handling, this is a safety net
        logger.critical(f"Task {self.request.id}: Unhandled exception during training job {training_job_id} execution: {e}", exc_info=True)
        # Ensure task is marked as failed if exception escapes run_job's finally block
        self.update_state(
            state='FAILURE',
            meta={
                'exc_type': type(e).__name__,
                'exc_message': str(e)
            }
        )
        # Re-raise to ensure Celery knows it failed critically
        raise

@shared_task(bind=True, name='tasks.hyperparameter_search')
def hyperparameter_search_task(self: Task, hp_search_job_id: int):
    """Celery task facade for hyperparameter search jobs."""
    logger.info(f"Task {self.request.id}: Received HP search request for Job ID {hp_search_job_id}")
    try:
        handler = HPSearchJobHandler(hp_search_job_id, self)
        return handler.run_job()
    except Exception as e:
        logger.critical(f"Task {self.request.id}: Unhandled exception during HP search job {hp_search_job_id} execution: {e}", exc_info=True)
        self.update_state(
            state='FAILURE',
            meta={
                'exc_type': type(e).__name__,
                'exc_message': str(e)
            }
        )
        raise

@shared_task(bind=True, name='tasks.inference')
def inference_task(self: Task, inference_job_id: int):
    """Celery task facade for inference jobs."""
    logger.info(f"Task {self.request.id}: Received inference request for Job ID {inference_job_id}")
    try:
        handler = InferenceJobHandler(inference_job_id, self)
        return handler.run_job()
    except Exception as e:
        logger.critical(f"Task {self.request.id}: Unhandled exception during inference job {inference_job_id} execution: {e}", exc_info=True)
        self.update_state(
            state='FAILURE',
            meta={
                'exc_type': type(e).__name__,
                'exc_message': str(e)
            }
        )
        raise