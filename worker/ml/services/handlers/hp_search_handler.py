# worker/ml/services/handlers/hp_search_handler.py
import asyncio
import logging
from typing import Any, Dict, Optional, Tuple  # Added Tuple

import optuna
import pandas as pd

from services.artifact_service import ArtifactService
from shared.core.config import settings
from shared.db.models import HyperparameterSearchJob  # DB model
from shared.repositories import (
    DatasetRepository,
    HPSearchJobRepository,
    MLFeatureRepository,
    ModelRepository,
    XaiResultRepository,
)
from shared.schemas.enums import (
    DatasetStatusEnum,
    JobStatusEnum,
    ModelTypeEnum,
    ObjectiveMetricEnum,
)
from shared.services import JobStatusUpdater

from ..factories.model_strategy_factory import create_model_strategy
from ..factories.optuna_factory import create_pruner, create_sampler
from ..hp_search_objective import Objective
from .base_handler import BaseMLJobHandler

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


class HPSearchJobHandler(BaseMLJobHandler):
    """Handles the execution of hyperparameter search jobs using injected dependencies."""

    def __init__(
        self,
        job_id: int,
        task_instance: Any,
        *,
        status_updater: JobStatusUpdater,
        model_repo: ModelRepository,
        xai_repo: XaiResultRepository,  # For base class
        feature_repo: MLFeatureRepository,  # For base class
        artifact_service: ArtifactService,
        dataset_repo: DatasetRepository,
        hp_search_job_repo: HPSearchJobRepository,
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
        self.hp_search_job_repo = hp_search_job_repo
        self._dataset_storage_path: Optional[str] = None
        self.job_config: Dict[str, Any] = {}  # Will hold HPSearchConfig data

    @property
    def job_type_name(self) -> str:
        return "HPSearchJob"

    @property
    def job_model_class(self) -> type:
        return HyperparameterSearchJob

    def _load_and_validate_job_details(self) -> bool:
        """Loads job record and config, ensures dataset is ready."""
        try:
            job_record = self.hp_search_job_repo.get_by_id(self.job_id)
            if not job_record:
                logger.error(f"{self.job_type_name} {self.job_id} not found.")
                self.status_updater.update_job_completion(
                    self.job_id,
                    self.job_model_class,
                    JobStatusEnum.FAILED,
                    f"Job record {self.job_id} not found.",
                )
                return False

            # For HP search, we might want to resume if it was PENDING, RUNNING,
            # or even if it previously FAILED or SUCCEEDED (if Optuna supports continuing such studies).
            # Optuna's load_if_exists handles this at the study level.
            # The main concern here is if the job definition itself is in a bad state.
            if job_record.status == JobStatusEnum.REVOKED:  # Don't resume revoked.
                logger.warning(f"Job {self.job_id} was REVOKED. Skipping.")
                return False

            self.job_db_record = job_record
            self.job_config = dict(
                job_record.config or {}
            )  # This IS HPSearchConfig data
            self.dataset_id = job_record.dataset_id

            if not self.dataset_id:
                raise ValueError("dataset_id missing from job record.")
            if not self.job_config:
                raise ValueError("Job config (HPSearchConfig) is empty or missing.")
            if not job_record.optuna_study_name:
                raise ValueError("Optuna study name missing from job record.")

            # Validate Dataset
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

            # Update status to RUNNING
            updated = self.status_updater.update_job_start(
                job_id=self.job_id,
                job_type=self.job_model_class,
                task_id=self.task.request.id,
            )
            if not updated:
                raise RuntimeError("Failed to update job status to RUNNING in DB.")

            logger.info(
                f"{self.job_type_name} {self.job_id} details loaded, status RUNNING."
            )
            return True

        except ValueError as ve:
            logger.error(f"Validation failed for HP Search Job {self.job_id}: {ve}")
            if self.job_id:
                self.status_updater.update_job_completion(
                    self.job_id, self.job_model_class, JobStatusEnum.FAILED, str(ve)
                )
            return False
        except RuntimeError as rte:
            logger.error(f"Runtime error for HP Search Job {self.job_id}: {rte}")
            return False
        except Exception as e:
            logger.error(
                f"Error loading HP Search Job {self.job_id} details: {e}", exc_info=True
            )
            if self.job_id:
                try:
                    self.status_updater.update_job_completion(
                        self.job_id,
                        self.job_model_class,
                        JobStatusEnum.FAILED,
                        f"Failed to load job details: {str(e)[:200]}",
                    )
                except Exception as db_err:
                    logger.error(
                        f"Failed to update DB status after loading error: {db_err}"
                    )
            return False

    def _load_data(self) -> pd.DataFrame:
        """Loads data using the injected artifact service."""
        if not self._dataset_storage_path:
            if not self.dataset_id:
                raise RuntimeError("Cannot load data: Dataset ID missing.")
            self._dataset_storage_path = self.dataset_repo.get_storage_path(
                self.dataset_id
            )
            if not self._dataset_storage_path:
                raise ValueError(
                    f"Storage path not found for Dataset {self.dataset_id}."
                )

        self._update_progress("Loading dataset artifact for HP search...", 15)
        df = self.artifact_service.load_dataframe_artifact(self._dataset_storage_path)
        if df is None or df.empty:
            raise ValueError(
                f"Failed to load or empty dataset from {self._dataset_storage_path}"
            )
        logger.info(
            f"HP Search: Dataset loaded from {self._dataset_storage_path}, shape: {df.shape}"
        )
        return df

    def _prepare_data(self, data: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepares X and y for HP search objective. (Same as TrainingHandler's method)"""
        logger.info("Preparing data for HP search objective...")
        if not self.job_config:
            raise RuntimeError("Job config (HPSearchConfig) not loaded.")

        # HPSearchConfig contains feature_columns and target_column directly
        features = self.job_config.get("feature_columns", [])
        target = self.job_config.get("target_column")

        if not features or not target:
            raise ValueError(
                "Missing feature_columns or target_column in HPSearchConfig."
            )

        missing_cols = [c for c in features + [target] if c not in data.columns]
        if missing_cols:
            raise ValueError(
                f"Dataset missing required columns for HP search: {', '.join(missing_cols)}"
            )

        X = data[features].copy()
        y = data[target].copy()

        if X.isnull().values.any():
            logger.warning(
                "HP Search: Feature data contains NaN values. Filling with 0."
            )
            X = X.fillna(0)
        if y.isnull().any():
            logger.warning(
                f"HP Search: Target column '{target}' has NaNs. Corresponding rows dropped."
            )
            valid_indices = y.notna()
            X = X[valid_indices]
            y = y[valid_indices]
            if y.empty:
                raise ValueError(
                    "HP Search: Target column is empty after removing NaN values."
                )

        if pd.api.types.is_bool_dtype(y):
            y = y.astype(int)
        elif not pd.api.types.is_numeric_dtype(y):
            try:
                y = pd.to_numeric(y, errors="raise")
            except (ValueError, TypeError) as e:
                raise TypeError(
                    f"HP Search: Target column '{target}' could not be converted to numeric: {e}"
                ) from e

        logger.info(f"HP Search: Prepared data - X shape {X.shape}, y shape {y.shape}")
        return X, y

    def _create_optuna_sampler(self) -> Optional[optuna.samplers.BaseSampler]:
        if not self.job_config:
            raise RuntimeError("Job config (HPSearchConfig) not loaded.")

        optuna_specific_config = self.job_config.get("optuna_config", {})
        if not isinstance(optuna_specific_config, dict):
            optuna_specific_config = {}  # Default if not a dict

        sampler_type_str = optuna_specific_config.get("sampler_type")  # Can be None
        sampler_params = optuna_specific_config.get("sampler_config", {})
        # Use random_seed from the main HPSearchConfig for sampler seed
        seed_for_sampler = self.job_config.get("random_seed", 42)
        return create_sampler(sampler_type_str, sampler_params, seed_for_sampler)

    def _create_optuna_pruner(self) -> Optional[optuna.pruners.BasePruner]:
        if not self.job_config:
            raise RuntimeError("Job config (HPSearchConfig) not loaded.")

        optuna_specific_config = self.job_config.get("optuna_config", {})
        if not isinstance(optuna_specific_config, dict):
            optuna_specific_config = {}

        pruner_type_str = optuna_specific_config.get("pruner_type")  # Can be None
        pruner_params = optuna_specific_config.get("pruner_config", {})
        # Seed is not typically passed to pruners
        return create_pruner(pruner_type_str, pruner_params)

    def _determine_optimization_direction(self) -> str:
        if not self.job_config:
            raise RuntimeError("Job config (HPSearchConfig) not loaded.")

        optuna_specific_config = self.job_config.get("optuna_config", {})
        if not isinstance(optuna_specific_config, dict):
            optuna_specific_config = {}

        metric_name_str = optuna_specific_config.get(
            "objective_metric", ObjectiveMetricEnum.F1_WEIGHTED.value
        )
        try:
            metric_enum = ObjectiveMetricEnum(metric_name_str)
        except ValueError:
            metric_enum = ObjectiveMetricEnum.F1_WEIGHTED  # Default

        # Most classification metrics we use are maximized.
        # If adding metrics like log_loss, this needs to be smarter.
        maximize_metrics = {
            ObjectiveMetricEnum.F1_WEIGHTED,
            ObjectiveMetricEnum.AUC,
            ObjectiveMetricEnum.PRECISION_WEIGHTED,
            ObjectiveMetricEnum.RECALL_WEIGHTED,
            ObjectiveMetricEnum.ACCURACY,
        }
        return "maximize" if metric_enum in maximize_metrics else "minimize"

    def _execute_hp_search(self, X: pd.DataFrame, y: pd.Series) -> optuna.Study:
        """Executes the Optuna study."""
        if not self.job_db_record or not self.job_config:
            raise RuntimeError("Job record or config not loaded.")

        optuna_storage_url = (
            str(settings.OPTUNA_DB_URL) if settings.OPTUNA_DB_URL else None
        )
        storage = (
            optuna.storages.RDBStorage(url=optuna_storage_url)
            if optuna_storage_url
            else None
        )

        study_name = self.job_db_record.optuna_study_name
        direction = self._determine_optimization_direction()
        sampler = self._create_optuna_sampler()
        pruner = self._create_optuna_pruner()

        logger.info(
            f"Creating/loading Optuna study: '{study_name}' "
            f"Direction: {direction}, Sampler: {sampler.__class__.__name__ if sampler else 'Default'}, "
            f"Pruner: {pruner.__class__.__name__ if pruner else 'Default'}"
        )
        study = optuna.create_study(
            study_name=study_name,
            storage=storage,
            load_if_exists=True,  # Important for resuming
            direction=direction,
            sampler=sampler,
            pruner=pruner,
        )

        # --- Prepare Objective ---
        # Get model_type_enum from HPSearchConfig
        model_type_str = self.job_config.get("model_type")
        if not model_type_str:
            raise ValueError("model_type missing in HPSearchConfig for Objective.")
        try:
            model_type_enum_for_objective = ModelTypeEnum(model_type_str)
        except ValueError:
            raise ValueError(f"Invalid model_type '{model_type_str}' for Objective.")

        hp_space_config_list = self.job_config.get("hp_space", [])
        if not hp_space_config_list:
            raise ValueError("hp_space not defined in HPSearchConfig.")

        # The Objective needs the HPSearchConfig (self.job_config) as base_job_config
        objective_instance = Objective(
            X,
            y,
            model_type_enum=model_type_enum_for_objective,
            hp_space_config=hp_space_config_list,
            base_job_config=self.job_config,  # Pass HPSearchConfig
            artifact_service=self.artifact_service,  # Pass injected service
        )

        optuna_specific_config = self.job_config.get("optuna_config", {})
        if not isinstance(optuna_specific_config, dict):
            optuna_specific_config = {}
        n_trials = optuna_specific_config.get("n_trials", 10)
        timeout_seconds = optuna_specific_config.get("timeout_seconds")  # Can be None

        async def progress_callback(
            study: optuna.Study, trial: optuna.trial.FrozenTrial
        ):
            # Calculate progress based on completed trials relative to n_trials
            # This doesn't account for timeout well, but is a simple progress indicator.
            progress_percent = (
                35 + int(60 * (len(study.trials) / n_trials)) if n_trials > 0 else 35
            )
            await self._update_progress(
                f"Optuna trial {trial.number + 1}/{n_trials} ({trial.state.name}). Current best: {study.best_value:.4f}",
                min(progress_percent, 95),  # Cap at 95% during search
            )

        logger.info(
            f"Starting Optuna study '{study_name}', optimizing for {n_trials} trials (timeout: {timeout_seconds}s)..."
        )
        study.optimize(
            objective_instance,
            n_trials=n_trials,
            timeout=timeout_seconds,
            callbacks=[progress_callback],
        )
        logger.info(f"Optuna study '{study_name}' optimization finished.")
        return study

    def _save_best_model(
        self, study: optuna.Study, X: pd.DataFrame, y: pd.Series
    ) -> Optional[int]:
        """Trains and saves the best model found by Optuna, if configured."""
        if not self.job_config.get("save_best_model", True):
            logger.info("Saving of best model is disabled by HPSearchConfig.")
            return None
        if not self.dataset_id:  # Should be set
            raise RuntimeError("Dataset ID missing. Cannot save best model.")

        try:
            best_trial = study.best_trial
        except ValueError:  # No trials completed or all failed
            logger.warning(
                "No best trial found in Optuna study. Cannot save best model."
            )
            return None

        logger.info(
            f"Best trial found: Number {best_trial.number}, Value: {best_trial.value:.4f}. Training final model..."
        )

        # Extract necessary configs from HPSearchConfig (self.job_config)
        hp_search_config_data = self.job_config
        model_type_str = hp_search_config_data.get("model_type")
        model_name_prefix = hp_search_config_data.get(
            "model_name"
        )  # Prefix for the saved model

        if not model_type_str or not model_name_prefix:
            raise ValueError(
                "model_type or model_name (prefix) missing in HPSearchConfig for saving best model."
            )
        try:
            model_type_enum = ModelTypeEnum(model_type_str)
        except ValueError:
            raise ValueError(
                f"Invalid model_type '{model_type_str}' for saving best model."
            )

        best_hyperparams = best_trial.params

        # The strategy's job_config can be the HPSearchConfig here, as it contains random_seed etc.
        final_strategy = create_model_strategy(
            model_type_enum,
            model_config=best_hyperparams,  # Best HPs found
            job_config=hp_search_config_data,  # Pass HPSearchConfig as job_config
            artifact_service=self.artifact_service,
        )

        logger.info(
            f"Training final model of type {model_type_enum.value} with best parameters: {best_hyperparams}"
        )
        train_result = final_strategy.train(
            X, y
        )  # X, y are from the full dataset loaded earlier
        logger.info(f"Final model trained. Performance metrics: {train_result.metrics}")

        new_model_id = -1
        try:
            latest_version = self.model_repo.find_latest_model_version(
                model_name_prefix
            )
            new_version = (latest_version or 0) + 1
            logger.info(f"Saving best model as '{model_name_prefix}' v{new_version}")

            model_data_for_db = {
                "name": model_name_prefix,
                "model_type": model_type_enum.value,
                "version": new_version,
                "description": f"Best model from HP Search Job {self.job_id} (Optuna Trial: {best_trial.number}, Value: {best_trial.value:.4f})",
                "hyperparameters": best_hyperparams,
                "performance_metrics": train_result.metrics,
                "dataset_id": self.dataset_id,
                "hp_search_job_id": self.job_id,  # Link back to this HP search job
                "s3_artifact_path": None,
            }
            new_model_id = self.model_repo.create_model_record(model_data_for_db)

            s3_uri = f"s3://{settings.S3_BUCKET_NAME}/models/{model_name_prefix}/v{new_version}/model.joblib"
            save_success = final_strategy.save_model(s3_uri)

            if not save_success:
                logger.critical(
                    f"Failed to save best model artifact to {s3_uri} AFTER creating DB record {new_model_id}."
                )
                raise IOError(f"Failed to save best model artifact to {s3_uri}")
            else:
                self.model_repo.set_model_artifact_path(new_model_id, s3_uri)
                logger.info(
                    f"Best model saved. DB ID: {new_model_id}, S3 Path: {s3_uri}"
                )

        except Exception as e:
            logger.error(
                f"Error during saving best model from HP Search Job {self.job_id}: {e}",
                exc_info=True,
            )
            if new_model_id > 0:
                logger.error(
                    f"Potential orphaned MLModel record for best model: ID {new_model_id}."
                )
            raise

        return new_model_id

    async def process_job(self) -> Dict:
        """Orchestrates the HP search job execution."""
        final_status = JobStatusEnum.FAILED
        status_message = "HP Search processing failed during initialization."
        results_payload: Dict[str, Any] = {
            "job_id": self.job_id,
            "status": final_status,
            "message": status_message,
        }
        best_model_id_saved: Optional[int] = None
        optuna_study_results: Dict[str, Any] = {}

        try:
            if not self._load_and_validate_job_details():
                if self.job_db_record and self.job_db_record.status not in [
                    JobStatusEnum.PENDING,
                    JobStatusEnum.RUNNING,
                    JobStatusEnum.FAILED,
                ]:
                    results_payload["status"] = JobStatusEnum.SKIPPED
                    results_payload["message"] = (
                        f"Job {self.job_id} was in a terminal state ({self.job_db_record.status.value}) and skipped."
                    )
                else:
                    results_payload["message"] = (
                        f"Job {self.job_id} failed validation or loading."
                    )
                return results_payload

            raw_data = self._load_data()
            await self._update_progress("Preparing data for HP search...", 35)
            X, y = self._prepare_data(raw_data)

            optuna_study = self._execute_hp_search(X, y)

            # Attempt to save the best model if configured
            best_model_id_saved = self._save_best_model(optuna_study, X, y)

            # Prepare results for DB update and Celery task
            try:
                best_trial_optuna = optuna_study.best_trial
                optuna_study_results = {
                    "best_trial_id": best_trial_optuna.number,
                    "best_params": best_trial_optuna.params,
                    "best_value": best_trial_optuna.value,
                    "best_ml_model_id": best_model_id_saved,  # This can be None
                }
                final_status = JobStatusEnum.SUCCESS
                status_message = f"HP search completed. Best trial: {best_trial_optuna.number} with value {best_trial_optuna.value:.4f}."
                if best_model_id_saved:
                    status_message += (
                        f" Best model saved with ID: {best_model_id_saved}."
                    )
            except ValueError:  # No best trial (e.g., all trials failed or pruned)
                final_status = JobStatusEnum.SUCCESS  # Study ran, but no "best" emerged
                status_message = "HP search finished, but no best trial was found (all trials may have failed or been pruned)."
                optuna_study_results = {"status_message": status_message}

            results_payload.update(optuna_study_results)
            results_payload["status"] = (
                JobStatusEnum.SUCCESS
            )  # Overall Celery task status
            results_payload["message"] = status_message

        except Exception as e:
            final_status = JobStatusEnum.FAILED
            status_message = (
                f"HP Search Job {self.job_id} failed: {type(e).__name__}: {e}"
            )
            logger.critical(status_message, exc_info=True)
            results_payload["error"] = str(e)
            results_payload["status"] = JobStatusEnum.FAILED
            results_payload["message"] = status_message

        finally:
            logger.info(
                f"Attempting final DB status update for HP Search Job {self.job_id} to {final_status.value}"
            )
            # Pass optuna_study_results which contains best_trial_id, params, value, and best_ml_model_id
            try:
                await asyncio.to_thread(
                    self.status_updater.update_job_completion,
                    job_id=self.job_id,
                    job_type=self.job_model_class,
                    status=final_status,
                    message=status_message,
                    results=optuna_study_results,  # Pass the dict with Optuna results
                )
            except Exception as db_err:
                logger.critical(
                    f"CRITICAL: Failed final DB update for HP Search Job {self.job_id} to status {final_status.value}: {db_err}",
                    exc_info=True,
                )

        return results_payload
