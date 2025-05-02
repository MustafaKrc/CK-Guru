# worker/ml/app/tasks.py
import logging
from typing import Dict, Optional, List, Any, Tuple
from celery import shared_task, Task
from celery.exceptions import Ignore, Terminated, Reject

import pandas as pd
import numpy as np
from sqlalchemy import select

# Import Handlers
from services.handlers.training_handler import TrainingJobHandler
from services.handlers.hp_search_handler import HPSearchJobHandler
from services.handlers.inference_handler import InferenceJobHandler

# Import DB services and session
from shared.db_session import get_sync_db_session
from services import job_db_service, xai_db_service
from services.artifact_service import artifact_service

# Import models and schemas
from shared.db.models import XAIResult, InferenceJob, MLModel, Dataset
from shared import schemas # Import root schemas
from shared.schemas.enums import (
    JobStatusEnum, XAITypeEnum, XAIStatusEnum, ModelTypeEnum, DatasetStatusEnum
)

# Import XAI Factory and Base Strategy
from services.factories.xai_strategy_factory import XAIStrategyFactory
from services.strategies.base_xai_strategy import BaseXAIStrategy # Import base

from services.feature_retriaval_service import feature_retrieval_service

# Import Celery app instance
from .main import celery_app

from shared.core.config import settings
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

# === Training and HP Search Tasks ===
@shared_task(bind=True, name='tasks.train_model', acks_late=True)
def train_model_task(self: Task, training_job_id: int):
    """Celery task facade for training jobs."""
    logger.info(f"Task {self.request.id}: Received training request for Job ID {training_job_id}")
    try:
        handler = TrainingJobHandler(training_job_id, self)
        return handler.run_job() # Handler manages DB/Celery state updates
    except (Ignore, Terminated, Reject) as e:
        raise e # Let Celery handle these
    except Exception as e:
        logger.critical(f"Task {self.request.id}: Unhandled exception in training handler {training_job_id}: {e}", exc_info=True)
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
        raise Reject(f"Unhandled handler error: {e}", requeue=False) from e

@shared_task(bind=True, name='tasks.hyperparameter_search', acks_late=True)
def hyperparameter_search_task(self: Task, hp_search_job_id: int):
    """Celery task facade for hyperparameter search jobs."""
    logger.info(f"Task {self.request.id}: Received HP search request for Job ID {hp_search_job_id}")
    try:
        handler = HPSearchJobHandler(hp_search_job_id, self)
        return handler.run_job() # Handler manages DB/Celery state updates
    except (Ignore, Terminated, Reject) as e:
        raise e # Let Celery handle these
    except Exception as e:
        logger.critical(f"Task {self.request.id}: Unhandled exception in HP search handler {hp_search_job_id}: {e}", exc_info=True)
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
        raise Reject(f"Unhandled handler error: {e}", requeue=False) from e

# === Refactored Inference Prediction Task ===
@shared_task(bind=True, name='tasks.inference_predict', acks_late=True)
def inference_predict_task(self: Task, inference_job_id: int):
    """
    Performs prediction using the provided features and triggers XAI orchestration.
    """
    task_id = self.request.id
    logger.info(f"Task {task_id}: Starting prediction task for InferenceJob ID {inference_job_id}")

    prediction_results_dict = None # Initialize
    features_df = None

    try:
        # --- Load Job Info & Features ---
        with get_sync_db_session() as session:
            job_record = job_db_service.get_job_for_worker(session, inference_job_id, "inference")
            if not job_record: raise Ignore(f"InferenceJob {inference_job_id} not found.")
            input_ref = job_record.input_reference if isinstance(job_record.input_reference, dict) else {}
            repo_id = input_ref.get('repo_id')
            commit_hash = input_ref.get('commit_hash')
            if not repo_id or not commit_hash:
                raise Reject(f"Missing repo_id or commit_hash in input_reference for job {inference_job_id}.", requeue=False)

            logger.info(f"Task {task_id}: Retrieving features for Repo={repo_id}, Commit={commit_hash[:7]}")
            features_df = feature_retrieval_service.get_features_for_commit(session, repo_id, commit_hash)

        if features_df is None or features_df.empty:
             raise Reject(f"Failed to retrieve features for Repo={repo_id}, Commit={commit_hash[:7]}.", requeue=False)

        # --- Run Prediction via Handler ---
        handler = InferenceJobHandler(inference_job_id, self)
        # Pass the loaded features DataFrame to the handler's run_job
        prediction_results_dict = handler.run_job(features_df) # Pass DataFrame

        # If handler.run_job succeeded without error, trigger XAI orchestration
        logger.info(f"Task {task_id}: Prediction successful for job {inference_job_id}. Triggering XAI orchestration.")
        orchestration_task_name = "tasks.orchestrate_xai"
        args = [inference_job_id]
        try:
            # Send task using this worker's celery app instance
            orchestration_task = celery_app.send_task(orchestration_task_name, args=args, queue="ml_queue") # Keep on ML queue
            if not orchestration_task or not orchestration_task.id:
                 logger.error(f"Task {task_id}: Failed to dispatch XAI orchestration task for job {inference_job_id} (invalid task returned).")
            else:
                 logger.info(f"Task {task_id}: Dispatched XAI orchestration task {orchestration_task.id} for job {inference_job_id}")
        except Exception as dispatch_err:
            logger.error(f"Task {task_id}: Failed to dispatch XAI orchestration task for job {inference_job_id}: {dispatch_err}", exc_info=True)
            # Log only, prediction was successful, don't fail this task

        return prediction_results_dict

    except Terminated as e:
        logger.warning(f"Task {task_id}: Prediction task terminated for job {inference_job_id}")
        # Handler should have updated DB status in its finally block
        raise e # Re-raise for Celery
    except Ignore as e:
        logger.info(f"Task {task_id}: Prediction task ignored for job {inference_job_id}: {e}")
         # Handler should have handled this
        raise e # Re-raise for Celery
    except Reject as e: # Catch Reject specifically if handler raises it
         logger.error(f"Task {task_id}: Prediction task rejected for job {inference_job_id}: {e}")
         # Handler should have updated DB status
         raise e # Re-raise
    except Exception as e:
        logger.critical(f"Task {task_id}: Unhandled exception in prediction task for job {inference_job_id}: {e}", exc_info=True)
        # Handler's finally block should update DB, but ensure Celery state is FAILURE
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
        raise Reject(f"Unhandled prediction error: {e}", requeue=False) from e


# === XAI Orchestration Task ===
@shared_task(bind=True, name='tasks.orchestrate_xai', acks_late=True)
def orchestrate_xai_task(self: Task, inference_job_id: int):
    """
    Orchestrates the generation of multiple XAI explanations for a completed inference job.
    Creates pending DB records and dispatches individual generation tasks.
    """
    task_id = self.request.id
    logger.info(f"Task {task_id}: Starting XAI orchestration for InferenceJob ID {inference_job_id}")

    dispatched_count = 0
    failed_dispatches = []

    try:
        with get_sync_db_session() as session:
            # --- Get Job & Model Info ---
            inference_job = job_db_service.get_job_for_worker(session, inference_job_id, "inference")
            if not inference_job:
                logger.warning(f"Task {task_id}: Orchestration skipped. Inference job {inference_job_id} not found.")
                raise Ignore("Inference job not found.")

            # Check status again - perhaps it changed between prediction and orchestration
            if inference_job.status != JobStatusEnum.SUCCESS:
                logger.warning(f"Task {task_id}: Orchestration skipped. Inference job {inference_job_id} status is {inference_job.status.value}, not SUCCESS.")
                raise Ignore("Inference job not successful.")

            model_record = session.get(MLModel, inference_job.ml_model_id)
            if not model_record:
                logger.error(f"Task {task_id}: ML Model {inference_job.ml_model_id} not found for job {inference_job_id}. Cannot orchestrate XAI.")
                # Fail the orchestration task if model is missing
                raise Reject("Associated ML Model not found.", requeue=False)

            # --- Determine Supported XAI Types ---
            # Simple example based on model type - expand as needed
            supported_types = [
                XAITypeEnum.SHAP,
                XAITypeEnum.FEATURE_IMPORTANCE,
                XAITypeEnum.LIME,
                XAITypeEnum.COUNTERFACTUALS
            ]
            if model_record.model_type == ModelTypeEnum.SKLEARN_RANDOMFOREST.value: # Check string value
                 if XAITypeEnum.DECISION_PATH not in supported_types:
                     supported_types.append(XAITypeEnum.DECISION_PATH)

            logger.info(f"Task {task_id}: Determined supported XAI types for model type '{model_record.model_type}': {[t.value for t in supported_types]}")

            # --- Create Pending Records & Prepare Dispatch Info ---
            created_xai_ids_map: Dict[XAITypeEnum, int] = {} # Store type -> id mapping
            tasks_to_dispatch: List[Dict[str, Any]] = []

            for xai_type in supported_types:
                # Check if this type already exists for the job (avoids duplicates if task reruns)
                existing_xai_id = xai_db_service.find_existing_xai_result_id_sync(session, inference_job_id, xai_type)
                if existing_xai_id:
                    logger.warning(f"Task {task_id}: XAI result record for type {xai_type.value} already exists (ID: {existing_xai_id}). Skipping creation/dispatch.")
                    continue

                # Create pending record
                xai_result_id = xai_db_service.create_pending_xai_result_sync(session, inference_job_id, xai_type)
                if xai_result_id:
                    created_xai_ids_map[xai_type] = xai_result_id
                    tasks_to_dispatch.append({"xai_result_id": xai_result_id, "xai_type": xai_type})
                else:
                    logger.error(f"Task {task_id}: Failed to create pending DB record for XAI type {xai_type.value}. It will not be generated.")

            # Commit pending records first
            if created_xai_ids_map:
                try:
                    session.commit()
                    logger.info(f"Task {task_id}: Committed {len(created_xai_ids_map)} pending XAI records for Job {inference_job_id}.")
                except Exception as commit_err:
                    logger.error(f"Task {task_id}: Failed to commit pending XAI records: {commit_err}", exc_info=True)
                    session.rollback()
                    raise Reject("Failed to create pending XAI records", requeue=False) from commit_err
            else:
                 logger.info(f"Task {task_id}: No new pending XAI records to create for job {inference_job_id}.")
                 # Exit successfully if no types needed processing
                 return {"status": "SUCCESS", "message": "No new XAI tasks needed.", "dispatched_count": 0}


            # Dispatch tasks *after* committing records
            task_name = "tasks.generate_explanation"
            xai_queue = "xai_queue" # Dedicated queue

            for task_info in tasks_to_dispatch:
                xai_result_id = task_info["xai_result_id"]
                xai_type = task_info["xai_type"]
                args = [xai_result_id]
                try:
                    task = celery_app.send_task(task_name, args=args, queue=xai_queue)
                    if task and task.id:
                        # Update XAI record with task ID immediately after dispatch
                        xai_db_service.update_xai_task_id_sync(session, xai_result_id, task.id)
                        dispatched_count += 1
                        logger.info(f"Task {task_id}: Dispatched XAI generation task {task.id} for Result ID {xai_result_id} ({xai_type.value}) to queue '{xai_queue}'.")
                    else:
                         logger.error(f"Task {task_id}: Dispatch for XAI Result {xai_result_id} returned invalid task object.")
                         failed_dispatches.append(xai_result_id)
                except Exception as dispatch_err:
                     logger.error(f"Task {task_id}: Failed dispatch for XAI Result {xai_result_id}: {dispatch_err}", exc_info=True)
                     failed_dispatches.append(xai_result_id)

            # Commit task ID updates and handle failed dispatches
            if dispatched_count > 0 or failed_dispatches:
                try:
                    if failed_dispatches:
                        xai_db_service.mark_xai_results_failed_sync(session, failed_dispatches, "Task dispatch failed")
                    session.commit()
                except Exception as final_commit_err:
                    logger.error(f"Task {task_id}: Failed final commit for task IDs/failed dispatches: {final_commit_err}", exc_info=True)
                    session.rollback() # Rollback if final commit fails

        logger.info(f"Task {task_id}: XAI Orchestration complete for job {inference_job_id}. Dispatched: {dispatched_count}, Failed Dispatches: {len(failed_dispatches)}.")
        return {"status": "SUCCESS", "dispatched_count": dispatched_count, "failed_dispatch_count": len(failed_dispatches)}

    except (Ignore, Reject) as e:
        logger.info(f"Task {task_id}: XAI Orchestration task ignored or rejected: {e}")
        raise e # Re-raise for Celery
    except Exception as e:
        logger.critical(f"Task {task_id}: XAI orchestration failed critically for job {inference_job_id}: {e}", exc_info=True)
        # No specific job status to update here, just log the failure and let Celery mark task as failed
        raise Reject(f"XAI orchestration failed: {e}", requeue=False) from e


# === Refactored Explanation Generation Task ===
@shared_task(bind=True, name='tasks.generate_explanation', acks_late=True)
def generate_explanation_task(self: Task, xai_result_id: int):
    """
    Generates a specific XAI explanation using the Strategy pattern.
    """
    task_id = self.request.id
    logger.info(f"Task {task_id}: Starting explanation generation for XAIResult ID {xai_result_id}")

    final_status = XAIStatusEnum.FAILED
    status_message = "Generation failed."
    result_data_json: Optional[Dict] = None
    session: Optional[Session] = None # Define session outside try

    try:
        with get_sync_db_session() as session:
            # --- 1. Load Records ---
            xai_record = xai_db_service.get_xai_result_sync(session, xai_result_id)
            if not xai_record:
                raise Ignore(f"XAIResult record {xai_result_id} not found.")
            if xai_record.status == XAIStatusEnum.RUNNING and xai_record.celery_task_id != task_id:
                raise Ignore(f"XAIResult {xai_result_id} already running under task {xai_record.celery_task_id}.")
            if xai_record.status in [XAIStatusEnum.SUCCESS, XAIStatusEnum.FAILED, XAIStatusEnum.REVOKED]:
                raise Ignore(f"XAIResult {xai_result_id} already in terminal state {xai_record.status.value}.")

            inference_job = job_db_service.get_job_for_worker(session, xai_record.inference_job_id, "inference")
            if not inference_job:
                raise ValueError(f"InferenceJob {xai_record.inference_job_id} not found.")
            ml_model_record = session.get(MLModel, inference_job.ml_model_id)
            if not ml_model_record or not ml_model_record.s3_artifact_path:
                raise ValueError(f"MLModel {inference_job.ml_model_id} or its artifact path not found.")
            input_ref = inference_job.input_reference if isinstance(inference_job.input_reference, dict) else {}
            repo_id = input_ref.get('repo_id')
            commit_hash = input_ref.get('commit_hash')
            if not repo_id or not commit_hash:
                 raise ValueError(f"Missing repo/commit info in inference job {inference_job.id}")

            # --- Update Status to RUNNING ---
            xai_db_service.update_xai_result_sync(session, xai_result_id, XAIStatusEnum.RUNNING, "Generation started", task_id=task_id, is_start=True, commit=True)

            # --- Load Model ---
            model = artifact_service.load_artifact(ml_model_record.s3_artifact_path)
            if not model: raise RuntimeError(...)

            # --- Load Features using FeatureRetrievalService ---
            logger.info(f"Task {task_id}: Retrieving features for XAI (Repo={repo_id}, Commit={commit_hash[:7]})")
            features_df = feature_retrieval_service.get_features_for_commit(session, repo_id, commit_hash)
            if features_df is None or features_df.empty:
                raise ValueError(f"Failed to retrieve features for XAI (Repo={repo_id}, Commit={commit_hash[:7]}).")

            # --- Prepare Data for XAI ---
            X_inference, identifiers_df = _prepare_data_for_xai(features_df, model) # Pass loaded df

            # --- Load Background Data (Conditional) ---
            background_data_df = _load_background_data_for_xai(session, ml_model_record.dataset_id, X_inference)

            # --- 6. Apply Strategy Pattern ---
            xai_type = xai_record.xai_type
            logger.info(f"Task {task_id}: Creating XAI strategy for type: {xai_type.value}")
            strategy: BaseXAIStrategy = XAIStrategyFactory.create(xai_type, model, background_data_df)
            logger.info(f"Task {task_id}: Executing explanation strategy: {strategy.__class__.__name__}")
            result_data_obj = strategy.explain(X_inference, identifiers_df) # Returns Pydantic model

            # Convert result object to JSON dict if successful
            if result_data_obj:
                result_data_json = result_data_obj.model_dump(exclude_none=True, mode='json')
                final_status = XAIStatusEnum.SUCCESS
                status_message = f"{xai_type.value} explanation generated successfully."
            else:
                 # Strategy might return None if explanation is not applicable or fails internally
                 final_status = XAIStatusEnum.FAILED
                 status_message = f"{xai_type.value} explanation generation failed or returned no data."

            # --- 7. Update Final Status in DB ---
            xai_db_service.update_xai_result_sync(session, xai_result_id, final_status, status_message, result_data_json, commit=True) # Commit final result

            logger.info(f"Task {task_id}: Finished generation for XAIResult {xai_result_id}. Status: {final_status.value}")
            return result_data_json # Return result data

    except Terminated as e:
        logger.warning(f"Task {task_id}: Terminated during explanation generation for XAIResult {xai_result_id}")
        # Update DB using sync helper (use new session for safety)
        try: xai_db_service.update_xai_result_sync(get_sync_db_session(), xai_result_id, XAIStatusEnum.FAILED, "Task terminated", commit=True)
        except Exception as db_err: logger.error(f"Failed DB update on Terminated: {db_err}")
        raise e # Re-raise for Celery
    except Ignore as e:
        logger.info(f"Task {task_id}: Ignoring task for XAIResult {xai_result_id}: {e}")
        raise e # Re-raise for Celery
    except Reject as e: # Catch Reject explicitly
         logger.error(f"Task {task_id}: Rejecting task for XAIResult {xai_result_id}: {e}")
         # DB status likely handled by code raising Reject
         raise e # Re-raise
    except Exception as e:
        session_available = 'session' in locals() and session is not None # Check if session was initialized
        if session_available: session.rollback() # Rollback if error occurred mid-processing
        status_message = f"Generation failed for XAIResult {xai_result_id}: {type(e).__name__}: {e}"
        logger.critical(f"Task {task_id}: {status_message}", exc_info=True)
        final_status = XAIStatusEnum.FAILED
        # Update DB status to FAILED using the sync helper (use new session for safety)
        try: xai_db_service.update_xai_result_sync(get_sync_db_session(), xai_result_id, final_status, status_message, commit=True)
        except Exception as db_err: logger.error(f"Failed DB update on Exception: {db_err}")
        # Ensure Celery state is FAILURE
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': status_message})
        raise Reject(status_message, requeue=False) from e


def _prepare_data_for_xai(features_df: pd.DataFrame, model: Any) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Separates features and identifiers, validates features."""
    identifier_cols = ['file', 'class_name'] # Use actual DB names
    identifiers_df = features_df[[col for col in identifier_cols if col in features_df.columns]].copy()
    expected_features = []
    if hasattr(model, 'feature_names_in_'): expected_features = model.feature_names_in_.tolist()
    if not expected_features:
        expected_features = features_df.columns.difference(identifier_cols).tolist() # Fallback
        logger.warning("Using inferred features for XAI preparation.")

    missing_features = set(expected_features) - set(features_df.columns)
    if missing_features: raise ValueError(f"Features missing for XAI: {missing_features}")

    X_inference = features_df[expected_features].fillna(0).copy() # Basic fillna
    return X_inference, identifiers_df

def _load_background_data_for_xai(session: Session, dataset_id: Optional[int], X_inference: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Loads background data from dedicated sample file or falls back."""
    if not dataset_id:
        logger.warning("No training dataset ID linked to model. Using inference data sample for background.")
        return X_inference.sample(min(100, len(X_inference)), random_state=42) if not X_inference.empty else None

    dataset: Dataset = session.get(Dataset, dataset_id)
    if not dataset:
         logger.warning(f"Training dataset record {dataset_id} not found. Using inference data sample.")
         return X_inference.sample(min(100, len(X_inference)), random_state=42) if not X_inference.empty else None
    


    background_path = dataset.background_data_path
    if not background_path:
        logger.warning(f"No background data path found for dataset {dataset_id}. Using inference data sample.")
        return X_inference.sample(min(100, len(X_inference)), random_state=42) if not X_inference.empty else None

    logger.info(f"Loading background data sample from: {background_path}")
    try:
        # Use artifact_service to load the DataFrame
        background_df = artifact_service.load_dataframe_artifact(background_path)
        if background_df is None or background_df.empty:
             logger.warning(f"Loaded background data from {background_path} is empty. Falling back.")
             raise ValueError("Empty background data") # Trigger fallback
        
        target_column = dataset.config.get('target_column')
        if target_column in background_df.columns:
            background_df = background_df.drop(columns=[target_column]) 

        logger.info(f"Loaded background data ({background_df.shape})")
        # Basic NaN handling consistent with feature prep
        return background_df.fillna(0)
    except Exception as e:
        logger.error(f"Failed to load background data from {background_path}: {e}", exc_info=True)
        logger.warning("Using inference data sample as fallback for background data.")
        return X_inference.sample(min(100, len(X_inference)), random_state=42) if not X_inference.empty else None
    