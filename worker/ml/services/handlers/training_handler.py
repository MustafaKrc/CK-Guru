# worker/ml/services/handlers/training_handler.py
import asyncio
import logging
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from services.artifact_service import ArtifactService
from shared.core.config import settings
from shared.db.models import TrainingJob
from shared.repositories import (
    DatasetRepository,
    MLFeatureRepository,
    ModelRepository,
    TrainingJobRepository,
    XaiResultRepository,
)
from shared.schemas.enums import DatasetStatusEnum, JobStatusEnum, ModelTypeEnum
from shared.services import JobStatusUpdater

from ..factories.model_strategy_factory import create_model_strategy
from ..strategies.base_strategy import BaseModelStrategy, TrainResult
from .base_handler import BaseMLJobHandler

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


class TrainingJobHandler(BaseMLJobHandler):
    """Handles model training jobs using injected dependencies and strategies."""

    def __init__(
        self,
        job_id: int,
        task_instance: Any,
        *,
        status_updater: JobStatusUpdater,
        model_repo: ModelRepository,
        xai_repo: XaiResultRepository,
        feature_repo: MLFeatureRepository,
        artifact_service: ArtifactService,
        dataset_repo: DatasetRepository,
        training_job_repo: TrainingJobRepository,
        **kwargs,
    ):
        super().__init__(
            job_id,
            task_instance,
            status_updater=status_updater,
            model_repo=model_repo,
            xai_repo=xai_repo,
            feature_repo=feature_repo,
            artifact_service=artifact_service,
        )
        self.dataset_repo = dataset_repo
        self.training_job_repo = training_job_repo
        self._dataset_storage_path: Optional[str] = None  # Cache path locally
        self.job_config: Dict[str, Any] = {}  # Initialize job_config, will be loaded

    @property
    def job_type_name(self) -> str:
        return "TrainingJob"

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
                    self.job_id,
                    self.job_model_class,
                    JobStatusEnum.FAILED,
                    f"Job record {self.job_id} not found.",
                )
                return False

            # Allow resuming previous studies for HP Search (already handled in HPSearchJobHandler)
            # For TrainingJob, if it's already SUCCESS/FAILED, typically skip.
            if job_record.status not in [JobStatusEnum.PENDING, JobStatusEnum.RUNNING]:
                logger.warning(
                    f"Job {self.job_id} is in a terminal state ({job_record.status.value}) and will not be re-processed."
                )
                # Return True to indicate it was loaded, but process_job might skip based on this.
                # Or return False if we strictly want to avoid any further processing.
                # For now, let's assume if it's terminal, we shouldn't proceed.
                return False  # Skip processing if already terminal

            self.job_db_record = job_record
            # Ensure config is a dictionary, even if None in DB
            self.job_config = dict(job_record.config or {})
            self.dataset_id = job_record.dataset_id

            if not self.dataset_id:
                raise ValueError("dataset_id missing from job record.")
            if (
                not self.job_config
            ):  # Check if job_config is empty after ensuring it's a dict
                raise ValueError("Job config is empty or missing from job record.")

            # --- Validate Dataset ---
            dataset_record = self.dataset_repo.get_record(self.dataset_id)
            if not dataset_record:
                raise ValueError(f"Dataset {self.dataset_id} record not found.")
            if dataset_record.status != DatasetStatusEnum.READY:
                raise ValueError(
                    f"Dataset {self.dataset_id} not READY (Status: {dataset_record.status.value})."
                )
            if not dataset_record.storage_path:
                raise ValueError(f"Dataset {self.dataset_id} storage path missing.")
            self._dataset_storage_path = dataset_record.storage_path

            # --- Update Status to RUNNING ---
            updated = self.status_updater.update_job_start(
                self.job_id, self.job_model_class, self.task.request.id
            )
            if not updated:  # If DB update fails
                raise RuntimeError("Failed to update job status to RUNNING in DB.")

            logger.info(
                f"{self.job_type_name} {self.job_id} details loaded, status set to RUNNING."
            )
            return True

        except ValueError as ve:
            logger.error(f"Validation failed for Training Job {self.job_id}: {ve}")
            if self.job_id:  # Ensure job_id is known before trying to update status
                self.status_updater.update_job_completion(
                    self.job_id, self.job_model_class, JobStatusEnum.FAILED, str(ve)
                )
            return False
        except RuntimeError as rte:  # Catch specific runtime error from status update
            logger.error(f"Runtime error for Training Job {self.job_id}: {rte}")
            # Status update failed, so can't update it again here reliably.
            return False
        except Exception as e:
            logger.error(
                f"Error loading Training Job {self.job_id} details: {e}", exc_info=True
            )
            if self.job_id:
                try:
                    self.status_updater.update_job_completion(
                        self.job_id,
                        self.job_model_class,
                        JobStatusEnum.FAILED,
                        f"Failed to load job details: {str(e)[:200]}",  # Truncate error
                    )
                except Exception as db_err:
                    logger.error(
                        f"Failed to update DB status after loading error: {db_err}"
                    )
            return False

    def _load_data(self) -> pd.DataFrame:
        """Loads data using the injected artifact service and cached path."""
        if not self._dataset_storage_path:
            if not self.dataset_id:  # Should be set by _load_and_validate_job_details
                raise RuntimeError("Cannot load data: Dataset ID is missing.")
            self._dataset_storage_path = self.dataset_repo.get_storage_path(
                self.dataset_id
            )
            if not self._dataset_storage_path:
                raise ValueError(
                    f"Storage path not found for Dataset {self.dataset_id}."
                )

        self._update_progress("Loading dataset artifact...", 15)
        df = self.artifact_service.load_dataframe_artifact(self._dataset_storage_path)
        if df is None or df.empty:
            raise ValueError(
                f"Failed to load or empty dataset from {self._dataset_storage_path}"
            )
        logger.info(
            f"Dataset loaded from {self._dataset_storage_path}, shape: {df.shape}"
        )
        return df

    def _prepare_data(self, data: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepares features (X) and target (y) for training."""
        logger.info("Preparing data for training...")
        if not self.job_config:  # Should be loaded by _load_and_validate_job_details
            raise RuntimeError("Job config not loaded. Cannot prepare data.")

        # Extract feature and target column names from job_config
        # The job_config here is the 'config' field of the TrainingJobDB,
        # which should match the TrainingConfig schema.
        training_config_data = (
            self.job_config
        )  # self.job_config IS the TrainingConfig dict

        features = training_config_data.get("feature_columns", [])
        target = training_config_data.get("target_column")

        if not features or not target:
            raise ValueError(
                "Missing feature_columns or target_column in job configuration."
            )

        missing_cols = [c for c in features + [target] if c not in data.columns]
        if missing_cols:
            raise ValueError(
                f"Dataset missing required columns: {', '.join(missing_cols)}"
            )

        X = data[features].copy()  # Use .copy() to avoid SettingWithCopyWarning
        y = data[target].copy()

        # Handle NaNs in features - simple fillna(0) for now
        if X.isnull().values.any():
            logger.warning("Feature data contains NaN values. Filling with 0.")
            X = X.fillna(0)

        if y.isnull().any():
            logger.warning(
                f"Target column '{target}' has NaNs. Corresponding rows will be dropped from X and y."
            )
            valid_indices = y.notna()
            X = X[valid_indices]
            y = y[valid_indices]
            if y.empty:  # Should not happen if dataset generation is robust
                raise ValueError("Target column is empty after removing NaN values.")

        # Ensure target is numeric (common requirement for sklearn classifiers)
        if pd.api.types.is_bool_dtype(y):
            y = y.astype(int)
        elif not pd.api.types.is_numeric_dtype(y):
            try:
                y = pd.to_numeric(y, errors="raise")
            except (ValueError, TypeError) as e:
                raise TypeError(
                    f"Target column '{target}' could not be converted to numeric: {e}"
                ) from e

        logger.info(f"Prepared training data: X shape {X.shape}, y shape {y.shape}")
        return X, y

    def _create_and_train_strategy(
        self, X_train: pd.DataFrame, y_train: pd.Series
    ) -> Tuple[TrainResult, BaseModelStrategy]:
        """Creates, validates, and trains the model strategy."""
        if not self.job_config:
            raise RuntimeError("Job config not loaded. Cannot create/train strategy.")

        training_config_data = (
            self.job_config
        )  # self.job_config is the TrainingConfig dict

        model_type_str = training_config_data.get("model_type")
        if not model_type_str:
            raise ValueError("model_type missing in job configuration.")
        try:
            model_type_enum = ModelTypeEnum(model_type_str)
        except ValueError:
            raise ValueError(
                f"Invalid model_type '{model_type_str}' in job configuration."
            )

        hyperparams = training_config_data.get("hyperparameters", {})

        # The main job_config (self.job_config which IS training_config_data) is passed as job_config to strategy
        # model_config for strategy is hyperparams
        strategy = create_model_strategy(
            model_type_enum,
            model_config=hyperparams,  # These are the specific HPs for the model
            job_config=training_config_data,  # Pass the whole TrainingConfig as job_config for strategy
            artifact_service=self.artifact_service,
        )

        # Hyperparameter validation (optional, strategy's _get_model_instance might do it)
        allowed_hp = strategy.get_hyperparameter_space()
        unknown_hp = set(hyperparams) - allowed_hp
        if unknown_hp:
            logger.warning(
                f"Unknown hyperparameters for {model_type_enum.value}: {sorted(list(unknown_hp))}. They will be ignored by scikit-learn."
            )
            raise ValueError(
                f"Unknown hyperparameters for {model_type_enum.value}: {sorted(list(unknown_hp))}"
            )

        self._update_progress(f"Training {model_type_enum.value} model...", 45)
        train_result = strategy.train(
            X_train, y_train
        )  # Strategy handles model fitting

        logger.info(
            f"Training complete for {model_type_enum.value}. Metrics: {train_result.metrics}"
        )
        return train_result, strategy

    def _save_results(
        self, train_result: TrainResult, strategy: BaseModelStrategy
    ) -> int:
        """Saves model artifact and creates DB record using injected repos/services."""
        if not self.job_config:
            raise RuntimeError("Job config not loaded. Cannot save results.")
        if not self.dataset_id:  # Should be set
            raise RuntimeError("Dataset ID missing. Cannot save results.")

        training_config_data = (
            self.job_config
        )  # self.job_config is the TrainingConfig dict

        model_name = training_config_data.get("model_name")
        model_type_str = training_config_data.get("model_type")
        hyperparams = training_config_data.get("hyperparameters", {})

        if not model_name or not model_type_str:
            raise ValueError(
                "Missing model_name or model_type in job configuration for saving."
            )
        try:
            model_type_enum = ModelTypeEnum(model_type_str)
        except ValueError:
            raise ValueError(f"Invalid model_type '{model_type_str}' for saving.")

        self._update_progress("Saving model artifact and record...", 90)
        new_model_id = -1  # Default to ensure it's defined

        try:
            latest_version = self.model_repo.find_latest_model_version(model_name)
            new_version = (latest_version or 0) + 1
            logger.info(
                f"Determined new model version for '{model_name}': v{new_version}"
            )

            model_data_for_db = {
                "name": model_name,
                "model_type": model_type_enum.value,
                "version": new_version,
                "description": f"Trained via TrainingJob {self.job_id}",
                "hyperparameters": hyperparams,
                "performance_metrics": train_result.metrics,
                "dataset_id": self.dataset_id,
                "training_job_id": self.job_id,
                "s3_artifact_path": None,  # Will be updated after successful save
            }
            # Pydantic model for creation if strict validation is desired before DB insert
            # model_create_schema = schemas.MLModelCreate(**model_data_for_db)
            # new_model_id = self.model_repo.create_model_record(model_create_schema.model_dump())
            new_model_id = self.model_repo.create_model_record(model_data_for_db)

            s3_uri = f"s3://{settings.S3_BUCKET_NAME}/models/{model_name}/v{new_version}/model.joblib"  # Use .joblib

            # The strategy instance already has the trained model in strategy.model
            save_success = strategy.save_model(
                s3_uri
            )  # Strategy uses its injected artifact_service

            if not save_success:
                logger.critical(
                    f"Failed to save model artifact to {s3_uri} AFTER creating DB record {new_model_id}."
                    " The database record may need manual correction or deletion."
                )
                # Attempt to delete the inconsistent DB record - this is complex.
                # Best effort: mark as failed or log for manual intervention.
                # For now, raising an error is crucial.
                raise IOError(f"Failed to save model artifact to {s3_uri}")
            else:
                self.model_repo.set_model_artifact_path(new_model_id, s3_uri)
                logger.info(
                    f"Model artifact saved to {s3_uri} and DB record {new_model_id} updated."
                )

        except Exception as e:
            logger.error(
                f"Error during saving model results for Training Job {self.job_id}: {e}",
                exc_info=True,
            )
            # If new_model_id was assigned, it means DB record might exist but artifact failed.
            if new_model_id > 0:
                logger.error(
                    f"Potential orphaned MLModel record: ID {new_model_id}. Artifact saving failed."
                )
            raise  # Re-raise to ensure the job is marked as FAILED

        return new_model_id

    async def process_job(self) -> Dict:
        """Orchestrates the training job execution."""
        final_status = JobStatusEnum.FAILED
        status_message = "Processing failed during initialization."
        results_payload: Dict[str, Any] = {
            "job_id": self.job_id,
            "status": final_status,
            "message": status_message,
        }
        new_model_id = None

        try:
            if not self._load_and_validate_job_details():
                # _load_and_validate_job_details already updates DB status on failure/skip
                # and returns False. So, we can compose the message for Celery result.
                if self.job_db_record and self.job_db_record.status not in [
                    JobStatusEnum.PENDING,
                    JobStatusEnum.RUNNING,
                    JobStatusEnum.FAILED,
                ]:
                    results_payload["status"] = JobStatusEnum.SKIPPED
                    results_payload["message"] = (
                        f"Job {self.job_id} was in a terminal state ({self.job_db_record.status.value}) and skipped."
                    )
                else:  # It failed loading or was invalid
                    results_payload["message"] = (
                        f"Job {self.job_id} failed validation or loading."
                    )
                    # results_payload["status"] remains FAILED
                return results_payload

            raw_data = self._load_data()

            await self._update_progress("Preparing data...", 35)
            X, y = self._prepare_data(raw_data)

            train_result, strategy_instance = self._create_and_train_strategy(X, y)

            new_model_id = self._save_results(train_result, strategy_instance)

            final_status = JobStatusEnum.SUCCESS
            status_message = f"Training successful. Model ID: {new_model_id} created."
            results_payload.update(
                {
                    "status": JobStatusEnum.SUCCESS,
                    "message": status_message,
                    "ml_model_id": new_model_id,
                    "metrics": train_result.metrics,
                }
            )

        except Exception as e:
            final_status = JobStatusEnum.FAILED
            status_message = (
                f"Training Job {self.job_id} failed: {type(e).__name__}: {e}"
            )
            logger.critical(status_message, exc_info=True)
            results_payload["error"] = str(e)  # For Celery task result
            results_payload["status"] = JobStatusEnum.FAILED
            results_payload["message"] = status_message

        finally:
            # This status update is critical. It reflects the final outcome of the handler's execution.
            logger.info(
                f"Attempting final DB status update for Training Job {self.job_id} to {final_status.value}"
            )
            completion_results_for_db = {}
            if final_status == JobStatusEnum.SUCCESS and new_model_id is not None:
                completion_results_for_db["ml_model_id"] = new_model_id

            try:
                await asyncio.to_thread(
                    self.status_updater.update_job_completion,
                    job_id=self.job_id,
                    job_type=self.job_model_class,
                    status=final_status,
                    message=status_message,
                    results=completion_results_for_db,
                )
            except Exception as db_err:
                logger.critical(
                    f"CRITICAL: Failed final DB update for Training Job {self.job_id} to status {final_status.value}: {db_err}",
                    exc_info=True,
                )
                # If DB update fails, the Celery task result should still reflect the handler's outcome.
                # The job status in DB might be stale (e.g., stuck in RUNNING).

        return results_payload
