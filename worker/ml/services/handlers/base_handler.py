# worker/ml/services/handlers/base_handler.py
import logging
import traceback
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import attributes
import pandas as pd
from celery import Task
from celery.exceptions import Ignore, Terminated
from sqlalchemy.orm import Session

# Import shared components
from shared.core.config import settings
from shared.schemas.enums import JobStatusEnum, DatasetStatusEnum
from shared.db_session import get_sync_db_session
from shared.utils.task_utils import update_task_state

# Import ML worker services
from .. import feature_db_service, job_db_service, model_db_service
from ..strategies.base_strategy import BaseModelStrategy
# Factory needed by subclasses
from ..factories.strategy_factory import create_model_strategy

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper()) 

class BaseMLJobHandler(ABC):
    """
    Abstract base class defining the template for handling ML jobs (Training, HP Search, Inference).
    """

    def __init__(self, job_id: int, task_instance: Task):
        """Initializes the handler."""
        self.job_id = job_id
        self.task = task_instance
        self.job_db_record = None  # Will hold the specific DB job record (TrainingJob, etc.)
        self.job_config: Dict[str, Any] = {}
        self.dataset_id: Optional[int] = None
        self.model_strategy: Optional[BaseModelStrategy] = None # Holds the algorithm strategy
        self.final_db_results: Dict[str, Any] = {} # Stores results to update DB on success/completion
        self.current_session: Optional[Session] = None # Holds session for use in steps

        logger.debug(f"Initialized {self.__class__.__name__} for Job ID {job_id}, Task ID {self.task.request.id if self.task else 'N/A'}")

    @property
    @abstractmethod
    def job_type_name(self) -> str:
        """Returns the specific job type name (e.g., 'TrainingJob', 'HPSearchJob')."""
        pass

    @property
    @abstractmethod
    def job_model_class(self) -> type:
        """Returns the SQLAlchemy model class for the specific job type."""
        pass

    def _update_progress(self, message: str, progress: int, state: str = 'STARTED'):
        """Helper to update Celery task state."""
        if self.task:
            logger.debug(f"Updating task {self.task.request.id} progress: {progress}%, State: {state}, Msg: {message}")
            try:
                update_task_state(self.task, state, message, progress)
            except Exception as e:
                 logger.error(f"Failed to update Celery task state: {e}", exc_info=True)
        else:
             logger.warning("Task instance not available for progress update.")

    def _update_db_status(self, session: Session, status: JobStatusEnum, message: str, commit: bool = True):
        # Infer job_type from class name for the service call
        job_type_str = self.job_type_name.lower().replace('job', '')
        logger.info(f"Updating DB status for Job {self.job_id} ({self.job_type_name}) to {status.value}. Message: {message[:100]}...")
        try:
            job_db_service.update_job_completion(
                session, self.job_id, job_type_str, status, message, self.final_db_results
            )
            if commit:
                session.commit()
                logger.debug(f"DB status update for Job {self.job_id} committed.")
        except Exception as e:
            logger.error(f"DB commit failed during status update for Job {self.job_id}.", exc_info=True)
            session.rollback()
            raise # Re-raise DB error

    # --- Template Method Steps ---

    def _load_job_details(self, session: Session):
        """Loads job details from DB and marks it as RUNNING."""
        logger.info(f"Loading details for {self.job_type_name} ID {self.job_id}")
        job_record = session.get(self.job_model_class, self.job_id)
        if not job_record:
            # If not found, raise Ignore immediately to stop processing
            # This prevents errors later if the job was deleted between dispatch and execution
            raise Ignore(f"{self.job_type_name} {self.job_id} not found in database. Ignoring task.")

        current_task_id = self.task.request.id if self.task else None

        # Check if already running by another task instance
        if job_record.status == JobStatusEnum.RUNNING and job_record.celery_task_id != current_task_id:
             # --- MODIFIED LOGIC ---
             logger.warning(f"Job {self.job_id} ({self.job_type_name}) status is RUNNING but with different Task ID ({job_record.celery_task_id}). "
                            f"Updating Task ID to current ({current_task_id}) and continuing.")
             # Update the task ID in the DB to reflect this worker is now handling it
             job_record.celery_task_id = current_task_id
             # Optionally update status message
             job_record.status_message = f"Processing taken over by Task ID: {current_task_id}"
             # DO NOT RAISE Ignore - Allow this worker to proceed
             # --- END MODIFIED LOGIC ---
        elif job_record.status not in [JobStatusEnum.PENDING, JobStatusEnum.RUNNING]: # Allow re-running PENDING or taking over RUNNING
             # If job is already SUCCESS, FAILED, REVOKED, ignore this task
             raise Ignore(f"Job {self.job_id} ({self.job_type_name}) has terminal status '{job_record.status.value}'. Ignoring task.")

        self.job_db_record = job_record

        # Check if the job record instance has a 'config' attribute before accessing it
        if hasattr(self.job_db_record, 'config') and self.job_db_record.config is not None:
            # Ensure it's treated as a dictionary
            self.job_config = dict(self.job_db_record.config) if isinstance(self.job_db_record.config, (dict, attributes.InstrumentedAttribute)) else {}
            logger.debug(f"Loaded job_config for Job {self.job_id}")
        else:
            self.job_config = {} # Default to empty dict if no config attribute
            logger.debug(f"No 'config' attribute found on Job {self.job_id} ({self.job_type_name}). Setting job_config to empty dict.")
            
        self.dataset_id = getattr(self.job_db_record, 'dataset_id', None)

        # Mark job as running (or update task ID if already running)
        job_db_service.update_job_start(session, self.job_db_record, current_task_id)
        session.commit() # Commit the status/task_id change
        session.refresh(self.job_db_record)
        logger.info(f"{self.job_type_name} {self.job_id} status set/confirmed as RUNNING with Task ID {current_task_id}.")

    def _load_data(self, session: Session) -> pd.DataFrame:
        """Loads dataset based on dataset_id. Can be overridden."""
        if self.dataset_id is None:
            raise ValueError("Dataset ID not available for loading data.")
        logger.info(f"Loading data for Dataset ID: {self.dataset_id}")

        status, path = feature_db_service.get_dataset_status_and_path(session, self.dataset_id)
        if status != DatasetStatusEnum.READY or not path:
            raise ValueError(f"Dataset {self.dataset_id} is not ready or its path is missing.")

        logger.info(f"Reading dataset parquet file from: {path}")
        try:
            df = pd.read_parquet(path, storage_options=settings.s3_storage_options)
            if df.empty:
                raise ValueError(f"Loaded dataset from {path} is empty.")
            logger.info(f"Dataset loaded successfully, shape: {df.shape}")
            return df
        except Exception as e:
            logger.error(f"Failed to read dataset parquet from {path}: {e}", exc_info=True)
            raise IOError(f"Failed to read dataset file: {e}") from e

    @abstractmethod
    def _prepare_data(self, data: pd.DataFrame) -> Any:
        """Abstract method to prepare data for the specific ML task."""
        pass

    @abstractmethod
    def _create_strategy(self) -> Optional[BaseModelStrategy]:
        """Abstract method to create the appropriate ML algorithm strategy."""
        pass

    @abstractmethod
    def _execute_core_ml_task(self, prepared_data: Any) -> Any:
        """Abstract method to execute the main ML logic (training, search, inference)."""
        pass

    @abstractmethod
    def _prepare_final_results(self, ml_result: Any):
        """
        Abstract method to process the result from _execute_core_ml_task.
        Should populate `self.final_db_results` and potentially save artifacts.
        DB commits for results should happen here or just before exiting the 'run_job' try block.
        """
        pass

    # --- Template Method ---
    def run_job(self) -> Dict:
        """
        Executes the ML job pipeline using the Template Method pattern.
        Handles overall execution flow, status updates, and error handling.
        """
        final_status = JobStatusEnum.FAILED # Default to failure
        final_db_status = JobStatusEnum.FAILED # Ensure final_db_status always defined
        status_message = "Job processing started but did not complete."
        task_was_ignored = False # Flag to track if Ignore was raised
        self.final_db_results = {'job_id': self.job_id}

        try:
            with get_sync_db_session() as session:
                self.current_session = session
                # Step 1: Load Job Details
                self._update_progress("Loading job details...", 5)
                self._load_job_details(session)

                # Step 2: Load Data
                self._update_progress("Loading data...", 15)
                raw_data = self._load_data(session) # Returns DataFrame for inference

                # Step 3: Create Strategy
                self._update_progress("Initializing strategy / Loading model...", 25)
                self.model_strategy = self._create_strategy()
                if self.model_strategy is None and self.job_type_name != 'HPSearchJob':
                     raise RuntimeError(f"Failed to create or load model strategy for {self.job_type_name}.")

                # Step 4: Prepare Data
                # Now returns features and optionally identifiers
                self._update_progress("Preparing data...", 35)
                prepared_data_package = self._prepare_data(raw_data)

                # Step 5: Execute Core Task
                # Pass the potentially modified prepared_data_package
                self._update_progress("Executing core ML task...", 45)
                ml_result_package = self._execute_core_ml_task(prepared_data_package) # Returns result, maybe ids

                # Step 6: Process & Save Results
                # Pass the potentially modified ml_result_package
                self._update_progress("Processing & saving results...", 90)
                self._prepare_final_results(ml_result_package)

                # --- Step 7: Set Final Success Status & Commit Results ---
                final_status = JobStatusEnum.SUCCESS
                final_db_status = JobStatusEnum.SUCCESS
                status_message = self.final_db_results.pop('status_message', "Job completed successfully.")
                self.final_db_results['status'] = 'SUCCESS'

                logger.info("Committing final ML task results to DB...")
                session.commit()

            self._update_progress(status_message, 100, state='SUCCESS')
            logger.info(f"Job {self.job_id} ({self.job_type_name}) completed successfully.")
            return self.final_db_results

        except Terminated as e:
            final_status = JobStatusEnum.REVOKED # Celery handles state, this is for DB
            final_db_status = JobStatusEnum.FAILED # Mark DB FAILED on revoke
            status_message = "Job terminated by request."
            logger.warning(f"Task {self.task.request.id}: {status_message}", exc_info=False)
            raise # Re-raise for Celery

        except Ignore as e:
             status_message = f"Job ignored: {e}"
             task_was_ignored = True # Set flag
             logger.info(f"Task {self.task.request.id}: {status_message}", exc_info=False)
             raise # Re-raise for Celery

        except Exception as e:
            # Log the CRITICAL error that occurred in the task
            final_db_status = JobStatusEnum.FAILED # Ensure DB status is FAILED
            status_message = f"Job failed: {type(e).__name__}: {e}"
            detailed_error = f"{status_message}\n{traceback.format_exc()}"
            logger.critical(f"Task {self.task.request.id}: {detailed_error}", exc_info=False) # Use critical for task errors
            self.final_db_results['error'] = detailed_error # Store error info for potential return

            raise # Re-raise exception to ensure Celery marks task as FAILURE

        finally:
            # --- Final DB Status Update ---
            # Always attempt to update the DB status unless the task was ignored.
            # We check if the current_session was successfully created before trying to use it
            # The status (final_db_status) is determined by the try/except blocks.
            if self.current_session: # Check if session was ever assigned
                try:
                    logger.info(f"Attempting final DB status update for Job {self.job_id} to {final_db_status.value}")
                    # Use a NEW session for safety, in case the original one is compromised
                    with get_sync_db_session() as final_session:
                        # Pass the correct lowercase job type string
                        job_type_str = self.job_type_name.lower().replace('job', '')
                        # Use the updated _update_db_status which calls the service correctly
                        self._update_db_status(final_session, final_db_status, status_message, commit=True)
                except Exception as db_err:
                    logger.critical(f"Task {self.task.request.id}: CRITICAL - Failed final DB status update for Job {self.job_id}: {db_err}", exc_info=True)
            elif task_was_ignored:
                logger.info(f"Task {self.task.request.id}: Skipped final DB status update because task was ignored.")
            else:
                 # This case should be rare if the initial loading succeeded
                 logger.error(f"Task {self.task.request.id}: Cannot perform final DB update for Job {self.job_id} because session was not initialized.")
