# worker/ml/services/handlers/hp_search_handler.py
import logging
from typing import Any, Dict, Optional, Tuple

import optuna
import pandas as pd

from services.artifact_service import ArtifactService
from shared import schemas
from shared.core.config import settings  # For Optuna DB URL
from shared.db.models import HyperparameterSearchJob
from shared.repositories import (
    DatasetRepository,
    HPSearchJobRepository,
    MLFeatureRepository,
    ModelRepository,
    XaiResultRepository,
)
from shared.schemas.enums import DatasetStatusEnum, JobStatusEnum

# Import Concrete types for type hints/injection
from shared.services import JobStatusUpdater

from ..factories.model_strategy_factory import create_model_strategy
from ..factories.optuna_factory import create_pruner, create_sampler
from ..hp_search_objective import Objective
from .base_handler import BaseMLJobHandler

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


class HPSearchJobHandler(BaseMLJobHandler):
    """Handles the execution of hyperparameter search jobs using injected dependencies."""

    # Inject specific repositories needed
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

            # Allow resuming studies that previously succeeded or failed
            if job_record.status not in [
                JobStatusEnum.PENDING,
                JobStatusEnum.RUNNING,
                JobStatusEnum.SUCCESS,
                JobStatusEnum.FAILED,
            ]:
                logger.warning(
                    f"Job {self.job_id} in unexpected state {job_record.status.value} for continuation. Skipping."
                )
                return False

            self.job_db_record = job_record
            self.job_config = dict(job_record.config or {})
            self.dataset_id = job_record.dataset_id
            if not self.dataset_id:
                raise ValueError("dataset_id missing.")
            if not self.job_config:
                raise ValueError("Job config missing.")
            if not job_record.optuna_study_name:
                raise ValueError("Optuna study name missing.")

            # --- Validate Dataset using DatasetRepository ---
            dataset_record = self.dataset_repo.get_record(self.dataset_id)
            if (
                not dataset_record
                or dataset_record.status != DatasetStatusEnum.READY
                or not dataset_record.storage_path
            ):
                status_val = (
                    dataset_record.status.value if dataset_record else "Not Found"
                )
                raise ValueError(
                    f"Dataset {self.dataset_id} not READY (Status: {status_val}) or path missing."
                )
            self._dataset_storage_path = dataset_record.storage_path

            updated = self.status_updater.update_job_start(
                job_id=self.job_id,
                job_type=self.job_model_class,
                task_id=self.task.request.id,
            )
            if not updated:
                raise RuntimeError("Failed status update to RUNNING.")

            logger.info(
                f"{self.job_type_name} {self.job_id} details loaded, status RUNNING."
            )
            return True

        except ValueError as ve:
            logger.error(f"Validation failed Job {self.job_id}: {ve}")
            self.status_updater.update_job_completion(
                self.job_id, self.job_model_class, JobStatusEnum.FAILED, str(ve)
            )
            return False
        except Exception as e:
            logger.error(f"Error loading job details {self.job_id}: {e}", exc_info=True)
            try:
                self.status_updater.update_job_completion(
                    self.job_id,
                    self.job_model_class,
                    JobStatusEnum.FAILED,
                    f"Failed load: {e}",
                )
            except Exception as db_err:
                logger.error(f"Failed DB update: {db_err}")
            return False

    def _load_data(self) -> pd.DataFrame:
        """Loads data using the injected artifact service."""
        if (
            not self._dataset_storage_path
        ):  # Path should be cached by _load_and_validate_job_details
            if not self.dataset_id:
                raise RuntimeError("Dataset ID missing.")
            # Fallback: get path using DatasetRepository if not cached (should not happen ideally)
            self._dataset_storage_path = self.dataset_repo.get_storage_path(
                self.dataset_id
            )
            if not self._dataset_storage_path:
                raise ValueError(
                    f"Storage path still not found for Dataset {self.dataset_id}."
                )

        dataset_path = self._dataset_storage_path

        self._update_progress("Loading dataset artifact...", 15)
        df = self.artifact_service.load_dataframe_artifact(dataset_path)
        if df is None or df.empty:
            raise ValueError(f"Failed load/empty dataset {dataset_path}")
        logger.info(f"Dataset loaded {dataset_path}, shape: {df.shape}")
        return df

    def _prepare_data(self, data: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepares X and y for HP search objective."""
        # (Identical logic to TrainingJobHandler's implementation)
        logger.info("Preparing data for HP search...")
        if not self.job_config:
            raise RuntimeError("Job config missing.")
        features = self.job_config.get("feature_columns", [])
        target = self.job_config.get("target_column")
        if not features or not target:
            raise ValueError("Missing features/target in config.")
        missing_cols = [c for c in features + [target] if c not in data.columns]
        if missing_cols:
            raise ValueError(f"Missing columns: {missing_cols}")

        X = data[features].fillna(0)
        y = data[target]
        if y.isnull().any():
            logger.warning(f"Target '{target}' has NaNs. Dropping rows.")
            mask = y.notna()
            X = X[mask]
            y = y[mask]
            if y.empty:
                raise ValueError("Target empty after NaN removal.")
        if pd.api.types.is_bool_dtype(y):
            y = y.astype(int)
        elif not pd.api.types.is_numeric_dtype(y):
            try:
                y = pd.to_numeric(y, errors="raise")
            except (ValueError, TypeError) as e:
                raise TypeError(f"Target '{target}' not numeric/bool: {e}") from e
        logger.info(f"Prepared HP search data: X={X.shape}, y={y.shape}")
        return X, y

    def _create_optuna_sampler(self) -> Optional[optuna.samplers.BaseSampler]:
        # (Logic remains the same, uses self.job_config)
        if not self.job_config:
            raise RuntimeError("Job config missing.")
        config = self.job_config.get("optuna_config", {})
        sampler_type_str = config.get("sampler_type")
        sampler_params = config.get("sampler_config", {})
        seed = self.job_config.get("random_seed", 42)
        return create_sampler(sampler_type_str, sampler_params, seed)

    def _create_optuna_pruner(self) -> Optional[optuna.pruners.BasePruner]:
        # (Logic remains the same, uses self.job_config)
        if not self.job_config:
            raise RuntimeError("Job config missing.")
        config = self.job_config.get("optuna_config", {})
        pruner_type_str = config.get("pruner_type")
        pruner_params = config.get("pruner_config", {})
        seed = self.job_config.get("random_seed", 42)
        return create_pruner(pruner_type_str, pruner_params, seed)

    def _determine_optimization_direction(self) -> str:
        # (Logic remains the same, uses self.job_config)
        if not self.job_config:
            raise RuntimeError("Job config missing.")
        opt_config = self.job_config.get("optuna_config", {})
        metric_name = opt_config.get(
            "objective_metric", schemas.ObjectiveMetricEnum.F1_WEIGHTED.value
        )
        maximize_metrics = {
            m.value for m in schemas.ObjectiveMetricEnum
        }  # Assuming maximize
        return "maximize" if metric_name in maximize_metrics else "minimize"

    def _execute_hp_search(self, X, y) -> optuna.Study:
        """Executes the Optuna study."""
        # (Logic remains the same, uses self._create_*, objective class, etc.)
        optuna_storage_url = settings.OPTUNA_DB_URL
        storage = (
            optuna.storages.RDBStorage(url=str(optuna_storage_url))
            if optuna_storage_url
            else None
        )
        study_name = self.job_db_record.optuna_study_name
        direction = self._determine_optimization_direction()
        if not study_name:
            raise ValueError("Optuna study name missing.")
        sampler = self._create_optuna_sampler()
        pruner = self._create_optuna_pruner()
        logger.info(
            f"Creating/loading study: '{study_name}' Dir:{direction} Sampler:{sampler.__class__.__name__} Pruner:{pruner.__class__.__name__}"
        )
        study = optuna.create_study(
            study_name=study_name,
            storage=storage,
            load_if_exists=True,
            direction=direction,
            sampler=sampler,
            pruner=pruner,
        )

        hp_space_config = self.job_config.get("hp_space", [])
        if not hp_space_config:
            raise ValueError("hp_space not defined.")
        objective = Objective(
            X, y, hp_space_config, self.job_config, self.artifact_service
        )
        optuna_config = self.job_config.get("optuna_config", {})
        n_trials = optuna_config.get("n_trials", 10)
        timeout = optuna_config.get("timeout_seconds")

        def progress_callback(study: optuna.Study, trial: optuna.trial.FrozenTrial):
            completed_or_stopped = len(study.trials)
            progress = (
                35 + int(60 * (completed_or_stopped / n_trials)) if n_trials > 0 else 35
            )
            self._update_progress(
                f"Optuna trial {trial.number+1}/{n_trials} ({trial.state.name})...",
                min(progress, 95),
            )

        logger.info(
            f"Starting Optuna optimize study '{study_name}', {n_trials} trials..."
        )
        study.optimize(
            objective, n_trials=n_trials, timeout=timeout, callbacks=[progress_callback]
        )
        logger.info(f"Optuna optimize finished study '{study_name}'.")
        return study

    def _save_best_model(self, study: optuna.Study, X, y) -> Optional[int]:
        """Trains and saves the best model found."""
        # (Logic remains the same, uses strategy factory, injected model_repo, artifact_service)
        if not self.job_config.get("save_best_model", True):
            return None
        logger.info("Training and saving best model...")
        try:
            best_trial = study.best_trial
        except ValueError:
            logger.warning("No best trial found.")
            return None

        try:
            hp_search_config = schemas.HPSearchConfig.model_validate(self.job_config)
            model_type_enum = hp_search_config.model_type
            model_name = hp_search_config.model_name
        except Exception as e:
            raise ValueError("Could not parse job config") from e

        best_hyperparams = best_trial.params
        final_strategy = create_model_strategy(
            model_type_enum, best_hyperparams, self.job_config, self.artifact_service
        )
        logger.info("Training final model with best parameters...")
        train_result = final_strategy.train(X, y)  # X,y passed in
        logger.info("Final model trained. Metrics: %s", train_result.metrics)

        new_model_id = -1
        try:
            # Use injected model_repo
            latest_version = self.model_repo.find_latest_model_version(model_name)
            new_version = (latest_version or 0) + 1
            logger.info(f"Saving best model '{model_name}' v{new_version}")
            model_data = {
                "name": model_name,
                "model_type": model_type_enum.value,
                "version": new_version,
                "description": f"Best from HP Search {self.job_id} (Trial: {best_trial.number}, Value: {best_trial.value:.4f})",
                "hyperparameters": best_hyperparams,
                "performance_metrics": train_result.metrics,
                "dataset_id": self.dataset_id,
                "hp_search_job_id": self.job_id,
                "s3_artifact_path": None,
            }
            new_model_id = self.model_repo.create_model_record(model_data)
            s3_uri = f"s3://{settings.S3_BUCKET_NAME}/models/{model_name}/v{new_version}/model.pkl"
            save_success = final_strategy.save_model(
                s3_uri
            )  # Strategy uses injected artifact_service
            if not save_success:
                logger.error("Failed save artifact. Rolling back DB.")
                raise IOError(f"Failed save model artifact {s3_uri}")
            else:
                self.model_repo.set_model_artifact_path(new_model_id, s3_uri)
                logger.info(f"Best model saved. DB ID: {new_model_id}, Path: {s3_uri}")
        except Exception as e:
            logger.error(
                f"Error _save_best_model job {self.job_id}: {e}", exc_info=True
            )
            raise

        return new_model_id

    def process_job(self) -> Dict:
        """Orchestrates the HP search job execution."""
        final_status = JobStatusEnum.FAILED
        status_message = "Processing failed"
        results_payload = {"job_id": self.job_id, "status": JobStatusEnum.FAILED}
        best_model_id = None
        study_results: Dict[str, Any] = {}

        try:
            # Step 1: Load Job Details & Validate & Set Running Status
            if not self._load_and_validate_job_details():
                return {
                    "status": (
                        JobStatusEnum.SKIPPED
                        if self.job_db_record
                        and self.job_db_record.status != JobStatusEnum.FAILED
                        else "FAILED"
                    ),
                    "message": f"Job {self.job_id} skipped or failed loading.",
                }

            # Step 2: Load Data
            raw_data = self._load_data()

            # Step 3: Prepare Data
            self._update_progress("Preparing data...", 35)
            X, y = self._prepare_data(raw_data)

            # Step 4: Execute HP Search
            study = self._execute_hp_search(X, y)

            # Step 5: Save Best Model (if configured)
            # This needs access to data (X, y) which were local to the try block
            # Pass X, y to the save method
            best_model_id = self._save_best_model(study, X, y)

            # Prepare results for DB update
            try:
                best_trial = study.best_trial
                study_results = {
                    "best_trial_id": best_trial.number,
                    "best_params": best_trial.params,
                    "best_value": best_trial.value,
                    "best_ml_model_id": best_model_id,
                }
                final_status = JobStatusEnum.SUCCESS
                status_message = (
                    f"HP search completed. Best trial: {best_trial.number}."
                )
                if best_model_id:
                    status_message += f" Model saved: {best_model_id}."
            except ValueError:  # No best trial
                final_status = (
                    JobStatusEnum.SUCCESS
                )  # Still success, just no best model
                status_message = "HP search finished, but no best trial found."
                study_results = {
                    "status_message": status_message
                }  # Store message in results for DB update

            results_payload.update(study_results)  # Add study results
            results_payload["status"] = JobStatusEnum.SUCCESS  # Overall status
            results_payload["message"] = status_message

        except Exception as e:
            final_status = JobStatusEnum.FAILED
            status_message = f"Job failed: {type(e).__name__}: {e}"
            logger.critical(
                f"HP Search Job {self.job_id} failed: {status_message}", exc_info=True
            )
            results_payload["error"] = status_message
            # Don't re-raise, let finally update DB

        finally:
            # --- Final DB Status Update ---
            logger.info(
                f"Attempting final DB update Job {self.job_id} to {final_status.value}"
            )
            # Pass study_results dict to be merged by updater
            try:
                self.status_updater.update_job_completion(
                    job_id=self.job_id,
                    job_type=self.job_model_class,
                    status=final_status,
                    message=status_message,
                    results=study_results,
                )
            except Exception as db_err:
                logger.critical(
                    f"CRITICAL: Failed final DB update Job {self.job_id}: {db_err}",
                    exc_info=True,
                )

        return results_payload  # Return payload for Celery task
