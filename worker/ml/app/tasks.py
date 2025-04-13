# worker/ml/app/tasks.py
import traceback
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import optuna
import pandas as pd
from celery import shared_task, Task
from celery.exceptions import Ignore, Terminated
from sqlalchemy import func

# Database and CRUD
from shared.db.models import Dataset, DatasetStatusEnum, TrainingJob, MLModel, HyperparameterSearchJob # Import specific models
from shared.db_session import get_sync_db_session
from shared.core.config import settings
from shared.utils.task_utils import update_task_state
from shared.schemas.ml_model import MLModelCreate, MLModelUpdate # Import schemas
from shared.db.models.inference_job import InferenceJob
from shared.db.models.training_job import JobStatusEnum

# Services and Utils
from services.artifact_service import artifact_service # Import the singleton instance
from services.training_service import get_trainer, TrainResult # Import factory and result tuple
from services import job_db_service, model_db_service, dataset_db_service

from services import job_db_service, model_db_service
from services.hp_search_service import Objective # Import the Objective class
from services.inference_service import InferenceService

# Use Celery's logger
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

@shared_task(bind=True, name='tasks.train_model')
def train_model_task(self: Task, training_job_id: int):
    task_id = self.request.id
    logger.info(f"Task {task_id}: Starting model training for TrainingJob ID: {training_job_id}")

    # Keep track of job info needed outside the initial session block
    job_config: Optional[Dict[str, Any]] = None
    #training_config: Optional[Dict[str, Any]] = None
    dataset_id: Optional[int] = None

    status_to_set = JobStatusEnum.FAILED
    status_message = "Task initialization failed."
    final_results_dict: Dict[str, Any] = {}

    result_payload = {'training_job_id': training_job_id, 'status': 'FAILED'} # Default payload

    try:
        # --- 1. Fetch Job Details & Update Initial Status ---
        with get_sync_db_session() as session:
            logger.info(f"Task {task_id}: Fetching training job details from DB.")
            job = session.get(TrainingJob, training_job_id)

            #job_db_service.update_job_start(session, job, task_id)

            if not job:
                raise ValueError(f"TrainingJob {training_job_id} not found.")
            if job.status == JobStatusEnum.RUNNING:
                raise Ignore(f"Job {training_job_id} already running.")

            logger.info(f"Task {task_id}: Updating job status to RUNNING.")
            job.status = JobStatusEnum.RUNNING
            job.celery_task_id = task_id
            job.started_at = datetime.now(timezone.utc)
            job.status_message = "Fetching dataset and preparing data..."
            session.commit()
            session.refresh(job) # Refresh to get committed state

            # --- Read necessary attributes into local variables BEFORE session closes ---
            status_message_for_update = job.status_message
            # job_config now DIRECTLY holds the TrainingConfig fields
            job_config = job.config if isinstance(job.config, dict) else {}
            # training_config = job_config.get('config', {}) # <-- REMOVE THIS LINE
            dataset_id = job.dataset_id
            # --- End Reading Attributes ---

        # --- Update Celery Task State AFTER session is closed ---
        # Now access the local variable `status_message_for_update`
        update_task_state(self, 'STARTED', status_message_for_update, 5)

        # --- Check if essential info was retrieved ---
        if dataset_id is None or job_config is None:
             raise ValueError("Failed to retrieve essential job configuration from database.")

        # --- 2. Load Dataset ---
        logger.info(f"Task {task_id}: Loading dataset ID: {dataset_id}")
        with get_sync_db_session() as session:
            # Use the service function which handles session internally
            dataset_status, dataset_s3_uri = dataset_db_service.get_dataset_status_and_path(session, dataset_id)
            if dataset_status != DatasetStatusEnum.READY or not dataset_s3_uri:
                raise ValueError(f"Dataset {dataset_id} not ready or path missing.")

        # Read parquet outside session
        df = pd.read_parquet(dataset_s3_uri, storage_options=settings.s3_storage_options)
        if df.empty: raise ValueError("Loaded dataset is empty.")
        logger.info(f"Task {task_id}: Loaded dataset shape {df.shape}")

        update_task_state(self, 'STARTED', "Dataset loaded. Preparing features...", 20)

        # --- 3. Prepare Data (X, y) ---
        # Use the local job_config variable
        feature_columns = job_config.get('feature_columns', [])
        target_column = job_config.get('target_column', [])
        if not feature_columns or not target_column: raise ValueError("Features/Target not specified in config.")
        missing_cols = [col for col in feature_columns + [target_column] if col not in df.columns]
        if missing_cols: raise ValueError(f"Dataset missing columns: {missing_cols}")

        X = df[feature_columns].fillna(0)
        y = df[target_column]
        if y.isnull().any():
            not_nan_mask = y.notna()
            X, y = X[not_nan_mask], y[not_nan_mask]
            if y.empty: raise ValueError(f"Target column all NaNs.")

        update_task_state(self, 'STARTED', "Data prepared. Initializing trainer...", 30)

        # --- 4. Instantiate Trainer & Train ---
        model_type = job_config.get('model_type')
        model_hyperparams = job_config.get('hyperparameters', {})
        if not model_type: raise ValueError("model_type not specified.")

        trainer = get_trainer(model_type, model_hyperparams, job_config)
        train_result: TrainResult = trainer.train(X, y)
        logger.info(f"Task {task_id}: Training complete. Metrics: {train_result.metrics}")

        update_task_state(self, 'STARTED', "Training complete. Saving artifacts...", 80)

        # --- 5. Save Artifact and Create DB Record ---
        # Use local job_config variable
        model_name = job_config.get('model_name')
        if not model_name: raise ValueError("model_name not specified.")

        with get_sync_db_session() as session:
            latest_version = model_db_service.find_latest_model_version(session, model_name)
            new_version = (latest_version or 0) + 1

            model_data = {
                'name': model_name, 'model_type': model_type, 'version': new_version,
                'description': f"Trained via TrainingJob {training_job_id}", # Use ID directly
                'hyperparameters': model_hyperparams, 'performance_metrics': train_result.metrics,
                'dataset_id': dataset_id, 'training_job_id': training_job_id,
            }
            new_model_id = model_db_service.create_model_record(session, model_data)

            artifact_filename = f"model_v{new_version}.pkl"
            s3_artifact_uri = f"s3://{settings.S3_BUCKET_NAME}/models/{model_name}/v{new_version}/{artifact_filename}"
            save_success = artifact_service.save_artifact(train_result.model, s3_artifact_uri)

            if not save_success:
                session.rollback()
                raise IOError("Failed to save model artifact")

            model_db_service.set_model_artifact_path(session, new_model_id, s3_artifact_uri)
            session.commit()

        # --- 6. Prepare Success Status ---
        status_to_set = JobStatusEnum.SUCCESS
        status_message = f"Training successful. Model ID: {new_model_id}."
        final_results_dict = {'ml_model_id': new_model_id}
        result_payload = {'training_job_id': training_job_id, 'status': 'SUCCESS', **final_results_dict}
        update_task_state(self, 'SUCCESS', status_message, 100)
        logger.info(f"Task {task_id}: {status_message}")
        return result_payload

    except Terminated:
        status_to_set = JobStatusEnum.REVOKED
        status_message = "Training task terminated."
        logger.warning(f"Task {task_id}: {status_message}")
        raise # Re-raise for Celery
    except Ignore:
         logger.info(f"Task {task_id}: Ignoring task execution.")
         raise # Re-raise for Celery
    except Exception as e:
        status_message = f"Training failed: {type(e).__name__}: {str(e)}"
        logger.error(f"Task {task_id}: {status_message}", exc_info=True)
        detailed_error = f"{status_message}\n{traceback.format_exc()}"
        result_payload['error'] = detailed_error
        # status_to_set remains FAILED
        raise # Re-raise for Celery

    finally:
        # --- Final DB Update ---
        try:
            with get_sync_db_session() as final_session:
                 # Use the specific job service function for update
                 job_db_service.update_job_completion(
                     final_session, training_job_id, 'training', status_to_set, status_message, final_results_dict
                 )
                 final_session.commit()
        except Exception as db_err:
            logger.error(f"Task {task_id}: CRITICAL - Failed to update final job status in DB: {db_err}", exc_info=True)

        # Update Celery state if not SUCCESS or REVOKED
        if status_to_set not in [JobStatusEnum.SUCCESS, JobStatusEnum.REVOKED]:
             try:
                 update_task_state(self, status_to_set.value.upper(), status_message, 0)
             except Exception as celery_update_err:
                 logger.error(f"Task {task_id}: Failed to update final Celery task state: {celery_update_err}")

# --- Hyperparameter Search Task ---
@shared_task(bind=True, name='tasks.hyperparameter_search')
def hyperparameter_search_task(self: Task, hp_search_job_id: int):
    """
    Celery task to perform hyperparameter search using Optuna.
    """
    task_id = self.request.id
    logger.info(f"Task {task_id}: Starting hyperparameter search for HPSearchJob ID: {hp_search_job_id}")

    # --- Initialize variables needed across scopes ---
    job_config: Optional[Dict[str, Any]] = None
    #hp_search_config: Optional[Dict[str, Any]] = None
    dataset_id: Optional[int] = None
    optuna_study_name: Optional[str] = None
    status_message_for_update: Optional[str] = None # For first update_task_state

    status_to_set = JobStatusEnum.FAILED
    status_message = "Task initialization failed."
    final_results_dict: Dict[str, Any] = {}
    result_payload = {'hp_search_job_id': hp_search_job_id, 'status': 'FAILED'}
    study: Optional[optuna.Study] = None

    try:
        # --- 1. Fetch Job Details & Update Initial Status ---
        with get_sync_db_session() as session:
            logger.info(f"Task {task_id}: Fetching HP search job details from DB.")
            job = session.get(HyperparameterSearchJob, hp_search_job_id)

            if not job:
                status_message = f"HyperparameterSearchJob with ID {hp_search_job_id} not found."
                logger.error(f"Task {task_id}: {status_message}")
                update_task_state(self, 'FAILURE', status_message, 0)
                raise ValueError(status_message)

            if job.status == JobStatusEnum.RUNNING:
                status_message = f"HP Search Job {hp_search_job_id} is already running (Task ID: {job.celery_task_id}). Skipping."
                logger.warning(f"Task {task_id}: {status_message}")
                update_task_state(self, 'REVOKED', status_message, 0)
                raise Ignore()

            logger.info(f"Task {task_id}: Updating job status to RUNNING.")
            # Use the service to update status cleanly
            job_db_service.update_job_start(session, job, task_id)
            session.commit()
            session.refresh(job) # Refresh after commit

            # --- Read necessary attributes into local variables ---
            status_message_for_update = job.status_message # Read message for Celery update
            job_config = job.config if isinstance(job.config, dict) else {}
            #hp_search_config = job_config.get('config', {})
            dataset_id = job.dataset_id
            optuna_study_name = job.optuna_study_name

        update_task_state(self, 'STARTED', status_message_for_update, 5)

        if dataset_id is None or not optuna_study_name:
            raise ValueError("Failed to retrieve essential HP search config (dataset_id, config, or study_name).")

        # --- 2. Load Dataset ---
        # (Similar to train_model_task - Reuse logic or refactor into a helper)
        logger.info(f"Task {task_id}: Loading dataset ID: {dataset_id}")
        with get_sync_db_session() as session:
            dataset = session.get(Dataset, dataset_id)
            if not dataset or not dataset.storage_path or dataset.status != DatasetStatusEnum.READY:
                status_message = f"Dataset ID {dataset_id} is not ready or has no storage path."
                raise ValueError(status_message)
            dataset_s3_uri = dataset.storage_path

        logger.info(f"Task {task_id}: Reading Parquet dataset from {dataset_s3_uri}")
        df = pd.read_parquet(dataset_s3_uri, storage_options=settings.s3_storage_options)
        if df.empty: raise ValueError("Loaded dataset is empty.")
        logger.info(f"Task {task_id}: Loaded dataset shape {df.shape}")

        update_task_state(self, 'STARTED', "Dataset loaded. Preparing features...", 15)

        # --- 3. Prepare Data (X, y) ---
        # (Similar to train_model_task)
        feature_columns = job_config.get('feature_columns', []) # Features might be defined here or inherit from dataset? Assuming here for now.
        target_column = job_config.get('target_column', 'is_buggy')

        if not feature_columns: # Need features defined in HP job config
             raise ValueError("feature_columns not specified in hp_search job config.")

        missing_cols = [col for col in feature_columns + [target_column] if col not in df.columns]
        if missing_cols: raise ValueError(f"Dataset missing required columns: {missing_cols}")

        X = df[feature_columns].fillna(0) # Handle NaNs
        y = df[target_column]
        if y.isnull().any():
            not_nan_mask = y.notna()
            X = X[not_nan_mask]
            y = y[not_nan_mask]
            if y.empty: raise ValueError(f"Target column '{target_column}' contains only NaN values after filtering.")

        update_task_state(self, 'STARTED', "Data prepared. Setting up Optuna study...", 25)

        # --- 4. Setup Optuna Study ---
        optuna_storage_url = settings.OPTUNA_DB_URL # Get from settings

        if not optuna_storage_url:
            # This shouldn't happen if config is right, but handle defensively
            logger.warning("Task {task_id}: OPTUNA_DB_URL not configured. Optuna will use in-memory storage (results will be lost).")
            storage = None
        else:
            storage = optuna.storages.RDBStorage(url=optuna_storage_url)

        optuna_config = job_config.get('optuna_config', {})
        direction = optuna_config.get('direction', 'maximize') # Default direction

        # TODO: Add Sampler/Pruner configuration based on optuna_config later if needed
        study = optuna.create_study(
            study_name=optuna_study_name,
            storage=storage,
            load_if_exists=True, # Continue existing study if name matches
            direction=direction,
            # pruner= # Add pruner instance based on config
            # sampler= # Add sampler instance based on config
        )
        logger.info(f"Task {task_id}: Optuna study '{optuna_study_name}' created/loaded. Direction: {direction}.")

        # --- 5. Define Objective & Optimize ---
        hp_space_config = job_config.get('hp_space', [])
        if not hp_space_config:
            raise ValueError("hp_space not defined in hp_search job config.")

        # Pass relevant parts of config to Objective
        base_trainer_config = {
            'model_type': job_config.get('model_type'),
            'random_seed': job_config.get('random_seed', 42),
            'hp_search_cv_folds': optuna_config.get('hp_search_cv_folds', 3), # Example CV config
            'optuna_config': optuna_config # Pass full Optuna config if needed by objective
        }
        objective = Objective(X, y, hp_space_config, base_trainer_config)
        n_trials = optuna_config.get('n_trials', 10) # Default trials

        # Add callback for progress updates? (More advanced)
        update_task_state(self, 'STARTED', f"Starting Optuna optimization ({n_trials} trials)...", 30)
        study.optimize(objective, n_trials=n_trials, timeout=job_config.get('timeout_seconds')) # Optional timeout

        logger.info(f"Task {task_id}: Optuna optimization complete for study '{optuna_study_name}'.")
        logger.info(f"Task {task_id}: Best trial: Number {study.best_trial.number}, Value: {study.best_value:.4f}")
        logger.info(f"Task {task_id}: Best Params: {study.best_params}")

        update_task_state(self, 'STARTED', "Optimization complete. Processing results...", 90)

        # --- 6. Save Best Model (Optional) ---
        save_best = job_config.get('save_best_model', True)
        best_model_db_id = None
        best_trial = None # Initialize best_trial to None

        try:
            # Check if there are any completed trials before accessing best_trial
            completed_trials = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
            if not completed_trials:
                logger.warning(f"Task {task_id}: No successfully completed trials found in study '{optuna_study_name}'. Cannot determine best trial.")
                status_message = "HP search finished, but no trials completed successfully."
            else:
                best_trial = study.best_trial # Get best_trial only if completed trials exist
                logger.info(f"Task {task_id}: Best trial found - Number {best_trial.number}, Value: {best_trial.value:.4f}")
                logger.info(f"Task {task_id}: Best Params: {best_trial.params}")
        except ValueError as e:
            # Catch potential errors during best_trial access, though the check above should prevent most
            logger.warning(f"Task {task_id}: Error accessing best trial even after check: {e}. No best trial determined.")
            status_message = f"HP search finished, but encountered error accessing best trial: {e}"

        # Proceed only if save_best is True AND a best_trial was successfully found
        if save_best and best_trial:
            logger.info(f"Task {task_id}: Training and saving best model from trial {best_trial.number}...")
            best_hyperparams = best_trial.params
            best_model_name = job_config.get('model_name') # Use base name from config
            model_type = job_config.get('model_type')

            # Re-train using best params on full dataset (or appropriate split)
            # Use the same trainer logic
            final_trainer = get_trainer(model_type, best_hyperparams, base_trainer_config)
            # Decide if final eval needed - here we just train on all data provided
            try:
                # Re-train on the whole dataset X, y used for the search
                final_model = final_trainer.model.set_params(**best_hyperparams).fit(X, y) # Set params and fit
                # Note: Evaluating this model requires a separate hold-out set not used in HP search
                final_metrics = {"info": "Trained on full search data with best params."}
                logger.info(f"Task {task_id}: Final model trained with best parameters.")

                # Save artifact and create DB record (similar to train_model_task)
                with get_sync_db_session() as session:
                    # Determine next version for the *model_name*
                    latest_version = session.query(func.max(MLModel.version)).filter(MLModel.name == best_model_name).scalar()
                    new_version = (latest_version or 0) + 1
                    logger.info(f"Task {task_id}: Saving best model as '{best_model_name}' v{new_version}")

                    model_create_schema = MLModelCreate(
                        name=best_model_name, model_type=model_type, version=new_version,
                        description=f"Best model from HP Search Job {hp_search_job_id} (Study: {optuna_study_name}, Trial: {best_trial.number})",
                        hyperparameters=best_hyperparams, performance_metrics=final_metrics, # Use actual metrics if evaluated
                        dataset_id=dataset_id, hp_search_job_id=hp_search_job_id, training_job_id=None,
                        s3_artifact_path=None # Set after save
                    )
                    best_ml_model_record = MLModel(**model_create_schema.model_dump())
                    session.add(best_ml_model_record)
                    session.flush()
                    best_model_db_id = best_ml_model_record.id

                    artifact_filename = f"model_v{new_version}.pkl" # Or joblib
                    s3_artifact_uri = f"s3://{settings.S3_BUCKET_NAME}/models/{best_model_name}/v{new_version}/{artifact_filename}"

                    save_success = artifact_service.save_artifact(final_model, s3_artifact_uri)
                    if not save_success:
                        session.rollback()
                        status_message = f"Failed to save best model artifact to {s3_artifact_uri}"
                        raise IOError(status_message)

                    best_ml_model_record.s3_artifact_path = s3_artifact_uri
                    session.add(best_ml_model_record)
                    session.commit() # Commit best model record creation/update
                    logger.info(f"Task {task_id}: Best model saved to DB (ID: {best_model_db_id}) and S3 ({s3_artifact_uri})")

            except Exception as final_train_err:
                 logger.error(f"Task {task_id}: Failed to train/save best model: {final_train_err}", exc_info=True)
                 # Continue without saving best model, but log error
                 status_message = f"HP search complete, but failed to save best model: {final_train_err}"
        elif save_best and not best_trial:
             logger.warning(f"Task {task_id}: Skipping saving best model because no successful trial was found.")
             # status_message might already be set from the check above
             status_message = status_message or "HP search finished, but no best trial found to save."

        # --- 7. Update Final Job Status ---
        with get_sync_db_session() as session:
             # Re-fetch job to attach to current session
             final_job = session.get(HyperparameterSearchJob, hp_search_job_id)
             if final_job:
                 # Determine final status based on whether a best trial was found
                 if best_trial:
                     final_job.status = JobStatusEnum.SUCCESS
                     final_job.best_trial_id = best_trial.number
                     final_job.best_params = best_trial.params
                     final_job.best_value = best_trial.value
                     final_job.best_ml_model_id = best_model_db_id # Link saved model ID if created
                     final_job.status_message = status_message if status_message and "Failed to save best model" in status_message else f"HP search completed successfully. Best trial: {best_trial.number}."
                 else:
                     # If no best trial, the search itself didn't fail, but wasn't successful in finding params
                     # Consider if FAILED is more appropriate if *no* trials completed
                     final_job.status = JobStatusEnum.FAILED # Or SUCCESS if partial success is okay
                     final_job.status_message = status_message or "HP search finished, but no trials completed successfully."

                 final_job.completed_at = datetime.now(timezone.utc)
                 session.commit()
                 status_to_set = final_job.status # Use the status set in the DB
                 status_message = final_job.status_message # Use updated message
             else:
                  logger.error(f"Task {task_id}: Could not find job {hp_search_job_id} for final update.")
                  status_message = "HP Search complete but failed to update final job status in DB."
                  status_to_set = JobStatusEnum.FAILED # Ensure failure state if DB update fails

        # Prepare result payload based on final status
        result_payload['status'] = status_to_set.value.upper()
        if best_trial:
            result_payload['best_trial_id'] = best_trial.number
            result_payload['best_value'] = best_trial.value
            result_payload['best_params'] = best_trial.params
            result_payload['best_ml_model_id'] = best_model_db_id
        else:
             result_payload['error'] = status_message # Include error/warning message

        update_task_state(self, result_payload['status'], status_message, 100)
        logger.info(f"Task {task_id}: {status_message}")

        # If the job ultimately failed, raise an exception for Celery
        if status_to_set == JobStatusEnum.FAILED:
            # Use a more specific exception if possible, otherwise generic
            raise Exception(status_message)

        return result_payload

    except Terminated:
         status_to_set = JobStatusEnum.REVOKED
         status_message = "HP search task terminated by revoke request."
         logger.warning(f"Task {task_id}: {status_message}")
         raise

    except Ignore:
         logger.info(f"Task {task_id}: Ignoring task execution as requested.")
         raise

    except Exception as e:
        error_type = type(e).__name__
        status_message = f"HP search failed due to {error_type}: {str(e)}"
        logger.error(f"Task {task_id}: {status_message}", exc_info=True)
        detailed_error = f"{status_message}\n{traceback.format_exc()}"
        result_payload['error'] = detailed_error
        raise

    finally:
        # --- Final DB Update (ensure status is set even on error) ---
        if status_to_set != JobStatusEnum.SUCCESS:
            try:
                with get_sync_db_session() as final_session:
                    final_job = final_session.get(HyperparameterSearchJob, hp_search_job_id)
                    if final_job and final_job.status != JobStatusEnum.SUCCESS:
                        logger.warning(f"Task {task_id}: Setting final job status to {status_to_set.value}. Message: {status_message}")
                        final_job.status = status_to_set
                        final_job.status_message = status_message[:1000]
                        if not final_job.completed_at:
                            final_job.completed_at = datetime.now(timezone.utc)
                        final_session.commit()
                    elif not final_job:
                         logger.error(f"Task {task_id}: Could not find job {hp_search_job_id} for final status update.")
            except Exception as db_err:
                logger.error(f"Task {task_id}: CRITICAL - Failed to update final job status in DB: {db_err}", exc_info=True)

        if status_to_set != JobStatusEnum.SUCCESS:
             try:
                 update_task_state(self, status_to_set.value.upper(), status_message, 0)
             except Exception as celery_update_err:
                 logger.error(f"Task {task_id}: Failed to update final Celery task state: {celery_update_err}")

# --- Inference Task ---
@shared_task(bind=True, name='tasks.inference')
def inference_task(self: Task, inference_job_id: int):
    """
    Celery task to perform inference using a specified ML model.
    """
    task_id = self.request.id
    logger.info(f"Task {task_id}: Starting inference for InferenceJob ID: {inference_job_id}")

    job: Optional[InferenceJob] = None
    status_to_set = JobStatusEnum.FAILED
    status_message = "Task initialization failed."
    final_results_dict: Dict[str, Any] = {} # Store prediction result for final update

    try:
        # --- 1. Fetch Job Details & Update Initial Status ---
        with get_sync_db_session() as session:
            logger.info(f"Task {task_id}: Fetching inference job details from DB.")
            # Need a get_job_for_worker supporting 'inference' or direct session.get
            job = session.get(InferenceJob, inference_job_id) # Direct get for now

            if not job:
                raise ValueError(f"InferenceJob {inference_job_id} not found.")
            if job.status == JobStatusEnum.RUNNING:
                raise Ignore(f"InferenceJob {inference_job_id} already running.")

            # Update status to RUNNING
            job.status = JobStatusEnum.RUNNING
            job.celery_task_id = task_id
            job.started_at = datetime.now(timezone.utc)
            job.status_message = "Loading model and preparing input..."
            session.commit()
            session.refresh(job)
            # Get necessary info after commit
            ml_model_id = job.ml_model_id
            input_reference = job.input_reference if isinstance(job.input_reference, dict) else {}

        update_task_state(self, 'STARTED', job.status_message, 5)

        # --- 2. Fetch Model Artifact Path ---
        with get_sync_db_session() as session:
            ml_model = session.get(MLModel, ml_model_id)
            if not ml_model or not ml_model.s3_artifact_path:
                raise ValueError(f"MLModel {ml_model_id} not found or has no artifact path.")
            model_artifact_path = ml_model.s3_artifact_path

        update_task_state(self, 'STARTED', "Model path retrieved. Preparing inference...", 15)

        # --- 3. Prepare Input Data ---
        # This is highly dependent on what `input_reference` contains.
        # Example: Assume it's a dictionary of feature values for a single prediction.
        # More complex cases: S3 path to data, list of inputs, commit hash requiring feature lookup etc.
        logger.info(f"Task {task_id}: Preparing input data from reference: {input_reference}")
        try:
            # --- !!! ---
            # --- !!! --- TODO: Adapt this logic based on expected input_reference structure ---
            # --- !!! --- Example: Direct feature dictionary
            # --- !!! ---
            if isinstance(input_reference, dict) and 'features' in input_reference:
                 # Assuming 'features' is a dict {feature_name: value}
                 input_df = pd.DataFrame([input_reference['features']])
                 # Ensure columns match model expectations - Requires loading model first OR
                 # storing expected feature list with the model artifact/record.
                 # This is deferred to the InferenceService for now.
                 logger.info(f"Task {task_id}: Prepared DataFrame from feature dictionary.")

            # Example: Reference to data stored elsewhere (needs implementation)
            # elif isinstance(input_reference, dict) and 's3_path' in input_reference:
            #     input_df = pd.read_parquet(input_reference['s3_path'], storage_options=settings.s3_storage_options)
            #     logger.info(f"Task {task_id}: Loaded input data from {input_reference['s3_path']}")

            else:
                 raise ValueError(f"Unsupported input_reference format: {input_reference}")

            if input_df.empty: raise ValueError("Prepared input data is empty.")

        except Exception as e:
            status_message = f"Failed to prepare input data: {e}"
            logger.error(f"Task {task_id}: {status_message}", exc_info=True)
            raise ValueError(status_message) from e

        update_task_state(self, 'STARTED', "Input prepared. Performing inference...", 40)

        # --- 4. Perform Inference ---
        inference_service = InferenceService(model_id=ml_model_id, artifact_path=model_artifact_path)
        prediction_result = inference_service.predict(input_df) # Service loads model internally

        logger.info(f"Task {task_id}: Inference successful. Result: {str(prediction_result)[:200]}...") # Log snippet
        update_task_state(self, 'STARTED', "Inference complete. Saving results...", 90)

        # --- 5. Update Final Job Status ---
        status_to_set = JobStatusEnum.SUCCESS
        status_message = "Inference successful."
        final_results_dict = {'prediction_result': prediction_result}
        result_payload = {'inference_job_id': inference_job_id, 'status': 'SUCCESS', **final_results_dict}
        update_task_state(self, 'SUCCESS', status_message, 100)
        logger.info(f"Task {task_id}: {status_message}")
        return result_payload

    except Terminated:
         status_to_set = JobStatusEnum.REVOKED
         status_message = "Inference task terminated."
         logger.warning(f"Task {task_id}: {status_message}")
         raise
    except Ignore:
         logger.info(f"Task {task_id}: Ignoring task execution.")
         raise
    except Exception as e:
        status_message = f"Inference failed: {type(e).__name__}: {str(e)}"
        logger.error(f"Task {task_id}: {status_message}", exc_info=True)
        detailed_error = f"{status_message}\n{traceback.format_exc()}"
        result_payload['error'] = detailed_error
        raise

    finally:
        # --- Final DB Update ---
        try:
            with get_sync_db_session() as final_session:
                # Need an update_job_completion supporting 'inference'
                # or use direct session update
                final_job = final_session.get(InferenceJob, inference_job_id)
                if final_job and final_job.status != JobStatusEnum.SUCCESS:
                     logger.warning(f"Task {task_id}: Setting final job status to {status_to_set.value}. Message: {status_message}")
                     final_job.status = status_to_set
                     final_job.status_message = status_message[:1000]
                     if status_to_set == JobStatusEnum.SUCCESS:
                         final_job.prediction_result = final_results_dict.get('prediction_result')
                     if not final_job.completed_at:
                         final_job.completed_at = datetime.now(timezone.utc)
                     final_session.commit()
                elif not final_job:
                     logger.error(f"Task {task_id}: Could not find job {inference_job_id} for final status update.")
        except Exception as db_err:
            logger.error(f"Task {task_id}: CRITICAL - Failed to update final job status in DB: {db_err}", exc_info=True)

        if status_to_set not in [JobStatusEnum.SUCCESS, JobStatusEnum.REVOKED]:
             try:
                 update_task_state(self, status_to_set.value.upper(), status_message, 0)
             except Exception as celery_update_err:
                 logger.error(f"Task {task_id}: Failed to update final Celery task state: {celery_update_err}")
