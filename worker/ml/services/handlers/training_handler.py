# worker/ml/services/handlers/training_handler.py
import logging
import traceback
from typing import Dict, Optional, Tuple, Any
import pandas as pd

from .base_handler import BaseMLJobHandler
from ..factories.model_strategy_factory import create_model_strategy
from ..strategies.base_strategy import BaseModelStrategy, TrainResult

from shared.db.models import TrainingJob, Dataset, MLModel
from shared.schemas.enums import JobStatusEnum, DatasetStatusEnum
from shared import schemas

from shared.services import JobStatusUpdater
from shared.repositories import ModelRepository, DatasetRepository, XaiResultRepository, MLFeatureRepository, TrainingJobRepository
from services.artifact_service import ArtifactService

from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

class TrainingJobHandler(BaseMLJobHandler):
    """Handles model training jobs using injected dependencies."""

    def __init__(self, job_id: int, task_instance: Any, *,
                 status_updater: JobStatusUpdater,
                 model_repo: ModelRepository,
                 xai_repo: XaiResultRepository,
                 feature_repo: MLFeatureRepository,
                 artifact_service: ArtifactService,
                 dataset_repo: DatasetRepository,
                 training_job_repo: TrainingJobRepository,
                 **kwargs):
        super().__init__(job_id, task_instance,
                         status_updater=status_updater,
                         model_repo=model_repo,
                         xai_repo=xai_repo,
                         feature_repo=feature_repo,
                         artifact_service=artifact_service)
        self.dataset_repo = dataset_repo 
        self.training_job_repo = training_job_repo
        self._dataset_storage_path: Optional[str] = None # Cache path locally

    @property
    def job_type_name(self) -> str:
        return 'TrainingJob'

    @property
    def job_model_class(self) -> type:
        return TrainingJob

    def _load_and_validate_job_details(self) -> bool:
        """Loads job record, config, and validates dataset readiness."""
        try:
            job_record = self.training_job_repo.get_by_id(self.job_id)
            if not job_record:
                logger.error(f"{self.job_type_name} {self.job_id} not found.")
                # Update status to FAILED if job definition is missing
                self.status_updater.update_job_completion(
                    self.job_id, self.job_model_class, JobStatusEnum.FAILED, f"Job record {self.job_id} not found."
                )
                return False

            # Allow resuming previous studies for HP Search (already handled in HPSearchJobHandler)
            # For TrainingJob, if it's already SUCCESS/FAILED, typically skip.
            if job_record.status not in [JobStatusEnum.PENDING, JobStatusEnum.RUNNING]:
                logger.warning(f"Job {self.job_id} in terminal state {job_record.status.value}. Skipping.")
                return False

            self.job_db_record = job_record
            self.job_config = dict(job_record.config or {})
            self.dataset_id = job_record.dataset_id
            if not self.dataset_id: raise ValueError("dataset_id missing from job record.")

            # --- Validate Dataset using injected DatasetRepository ---
            dataset_record = self.dataset_repo.get_record(self.dataset_id)
            if not dataset_record:
                raise ValueError(f"Dataset {self.dataset_id} record not found.")
            if dataset_record.status != DatasetStatusEnum.READY:
                raise ValueError(f"Dataset {self.dataset_id} not READY (Status: {dataset_record.status.value}).")
            if not dataset_record.storage_path:
                raise ValueError(f"Dataset {self.dataset_id} storage path missing.")
            self._dataset_storage_path = dataset_record.storage_path # Cache path

            # --- Update status using injected JobStatusUpdater ---
            updated = self.status_updater.update_job_start(
                self.job_id, self.job_model_class, self.task.request.id
            )
            if not updated: raise RuntimeError("Failed status update to RUNNING.")

            # No need to reload job record after status update via service

            logger.info(f"{self.job_type_name} {self.job_id} details loaded, status RUNNING.")
            return True

        except ValueError as ve:
             logger.error(f"Validation failed Job {self.job_id}: {ve}")
             self.status_updater.update_job_completion(
                 self.job_id, self.job_model_class, JobStatusEnum.FAILED, str(ve)
             )
             return False
        except Exception as e:
             logger.error(f"Error loading job details {self.job_id}: {e}", exc_info=True)
             try: self.status_updater.update_job_completion(self.job_id, self.job_model_class, JobStatusEnum.FAILED, f"Failed load: {e}")
             except Exception as db_err: logger.error(f"Failed DB update: {db_err}")
             return False

    def _load_data(self) -> pd.DataFrame:
        """Loads data using the injected artifact service and cached path."""
        if not self._dataset_storage_path:
            # Path should have been set in _load_and_validate_job_details
            # Fetch it again if missing (shouldn't happen ideally)
            if not self.dataset_id: raise RuntimeError("Dataset ID missing.")
            self._dataset_storage_path = self.dataset_repo.get_storage_path(self.dataset_id)
            if not self._dataset_storage_path:
                raise ValueError(f"Storage path not found Dataset {self.dataset_id}.")

        dataset_path = self._dataset_storage_path
        self._update_progress("Loading dataset artifact...", 15)
        df = self.artifact_service.load_dataframe_artifact(dataset_path) # Use injected service
        if df is None or df.empty: raise ValueError(f"Failed load/empty dataset from {dataset_path}")
        logger.info(f"Dataset loaded from {dataset_path}, shape: {df.shape}")
        return df

    def _prepare_data(self, data: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepares features (X) and target (y) for training."""
        # Logic remains the same, no DB access needed here
        logger.info("Preparing data for training...")
        # ... (rest of prep logic) ...
        if not self.job_config: raise RuntimeError("Job config not loaded.")
        features = self.job_config.get('feature_columns', [])
        target = self.job_config.get('target_column')
        if not features or not target: raise ValueError("Missing feature_columns or target_column.")
        missing_cols = [c for c in features + [target] if c not in data.columns]
        if missing_cols: raise ValueError(f"Missing columns: {missing_cols}")

        X = data[features].fillna(0)
        y = data[target]
        if y.isnull().any():
            logger.warning(f"Target '{target}' has NaNs. Dropping rows.")
            mask = y.notna(); X = X[mask]; y = y[mask]
            if y.empty: raise ValueError("Target empty after NaN removal.")
        if pd.api.types.is_bool_dtype(y): y = y.astype(int)
        elif not pd.api.types.is_numeric_dtype(y):
            try: y = pd.to_numeric(y, errors='raise')
            except (ValueError, TypeError) as e: raise TypeError(f"Target '{target}' not numeric/bool: {e}") from e
        logger.info(f"Prepared training data: X={X.shape}, y={y.shape}")
        return X, y

    def _create_and_train_strategy(self, X_train, y_train) -> Tuple[TrainResult, BaseModelStrategy]:
        """Creates, validates, and trains the model strategy."""
        # Logic remains the same, uses self.job_config and self.artifact_service
        if not self.job_config: raise RuntimeError("Job config needed.")
        model_type_enum = self.job_config.get('model_type')
        hyperparams = self.job_config.get('hyperparameters', {})
        if not isinstance(model_type_enum, schemas.ModelTypeEnum):
            try: model_type_enum = schemas.ModelTypeEnum(str(model_type_enum))
            except ValueError: raise ValueError(f"Invalid model_type '{model_type_enum}'.")

        # Pass artifact_service during creation
        strategy = create_model_strategy(model_type_enum, hyperparams, self.job_config, self.artifact_service)
        allowed = strategy.get_hyperparameter_space()
        unknown = set(hyperparams) - allowed
        if unknown: raise ValueError(f"Unknown hyperparameters: {sorted(unknown)}")

        self._update_progress("Training model...", 45)
        train_result = strategy.train(X_train, y_train) # Strategy handles model fitting
        return train_result, strategy

    def _save_results(self, train_result: TrainResult, strategy: BaseModelStrategy) -> int:
        """Saves model artifact and creates DB record using injected repos/services."""
        if not self.job_config: raise RuntimeError("Job config needed.")
        model_name = self.job_config.get('model_name')
        model_type_enum: Optional[schemas.ModelTypeEnum] = schemas.ModelTypeEnum(self.job_config.get('model_type'))
        hyperparams = self.job_config.get('hyperparameters', {})
        if not model_name or not isinstance(model_type_enum, schemas.ModelTypeEnum):
            raise ValueError("Missing/invalid model_name or model_type.")

        self._update_progress("Saving model artifact and record...", 90)
        new_model_id = -1

        # --- Perform DB operations ---
        # These methods handle their own sessions internally.
        # This sequence requires careful error handling if atomicity is crucial.
        try:
            # 1. Find latest version (Read operation)
            latest_version = self.model_repo.find_latest_model_version(model_name)
            new_version = (latest_version or 0) + 1
            logger.info(f"Saving model '{model_name}' v{new_version}")

            # 2. Create DB record (Write operation)
            model_data = {
                'name': model_name, 'model_type': model_type_enum.value, 'version': new_version,
                'description': f"Trained via TrainingJob {self.job_id}",
                'hyperparameters': hyperparams, 'performance_metrics': train_result.metrics,
                'dataset_id': self.dataset_id, 'training_job_id': self.job_id,
                's3_artifact_path': None
            }
            new_model_id = self.model_repo.create_model_record(model_data)

            # 3. Save artifact (External operation)
            s3_uri = f"s3://{settings.S3_BUCKET_NAME}/models/{model_name}/v{new_version}/model.pkl"
            save_success = strategy.save_model(s3_uri) # Strategy uses injected artifact_service

            if not save_success:
                # TODO: How to handle rollback? The model record is already committed.
                # Option A: Delete the created model record (requires another repo call).
                # Option B: Leave the record but without an artifact path (less ideal).
                # Option C: Implement Unit of Work pattern for atomicity (more complex).
                # Let's log a critical error for now and raise.
                logger.critical(f"Failed to save artifact {s3_uri} AFTER creating DB record {new_model_id}. Manual cleanup may be needed.")
                raise IOError(f"Failed to save model artifact to {s3_uri}")
            else:
                # 4. Update DB record with path (Write operation)
                self.model_repo.set_model_artifact_path(new_model_id, s3_uri)
                logger.info(f"Model saved. DB ID: {new_model_id}, Path: {s3_uri}")

        except Exception as e:
             # Catch errors during any step (DB or artifact save)
             logger.error(f"Error during saving results for job {self.job_id}: {e}", exc_info=True)
             # If model record was potentially created but artifact failed, attempt cleanup?
             # This area needs robust handling based on desired atomicity.
             raise # Re-raise the exception

        return new_model_id

    def process_job(self) -> Dict:
        """Orchestrates the training job execution."""
        final_status = JobStatusEnum.FAILED
        status_message = "Processing failed"
        results_payload = {'job_id': self.job_id, 'status': JobStatusEnum.FAILED}
        new_model_id = None

        try:
            if not self._load_and_validate_job_details():
                 return {'status': JobStatusEnum.SKIPPED, 'message': f"Job {self.job_id} skipped/failed loading."}
            raw_data = self._load_data()
            self._update_progress("Preparing data...", 35)
            X, y = self._prepare_data(raw_data)
            train_result, strategy_instance = self._create_and_train_strategy(X, y)
            new_model_id = self._save_results(train_result, strategy_instance)

            final_status = JobStatusEnum.SUCCESS
            status_message = f"Training successful. Model ID: {new_model_id}."
            results_payload.update({'status': JobStatusEnum.SUCCESS, 'message': status_message, 'ml_model_id': new_model_id})

        except Exception as e:
            final_status = JobStatusEnum.FAILED
            status_message = f"Job failed: {type(e).__name__}: {e}"
            logger.critical(f"Training Job {self.job_id} failed: {status_message}", exc_info=True)
            results_payload['error'] = status_message

        finally:
            logger.info(f"Attempting final DB status update Job {self.job_id} to {final_status.value}")
            completion_results = {'ml_model_id': new_model_id} if final_status == JobStatusEnum.SUCCESS else None
            try: # Use injected status_updater
                 self.status_updater.update_job_completion(
                      self.job_id, self.job_model_class, final_status, status_message, results=completion_results
                 )
            except Exception as db_err:
                  logger.critical(f"CRITICAL: Failed final DB update Job {self.job_id}: {db_err}", exc_info=True)

        return results_payload