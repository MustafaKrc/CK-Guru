# worker/ml/services/handlers/hp_search_handler.py
import logging
from typing import Any, Tuple, Dict, Optional
import pandas as pd

import optuna

from .base_handler import BaseMLJobHandler
from ..factories.strategy_factory import create_model_strategy
from ..strategies.base_strategy import BaseModelStrategy, TrainResult
from ..hp_search_objective import Objective
from ..factories.optuna_factory import create_sampler, create_pruner

from shared.db.models import HyperparameterSearchJob, MLModel, JobStatusEnum
from shared.core.config import settings
from shared import schemas

from .. import model_db_service, job_db_service

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)

class HPSearchJobHandler(BaseMLJobHandler):
    """Handles the execution of hyperparameter search jobs using Optuna."""

    @property
    def job_type_name(self) -> str:
        return 'HPSearchJob'

    @property
    def job_model_class(self) -> type:
        return HyperparameterSearchJob

    def _prepare_data(self, data: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepares features (X) and target (y) for HP search objective."""
        logger.info("Preparing data for hyperparameter search...")

        # Ensure job_config is loaded (should be done by BaseHandler._load_job_details)
        if not self.job_config:
            raise RuntimeError("Job config not loaded in HP search handler.")

        # Feature/target columns might be defined directly in HP search config
        # or inherited from the dataset config. Prioritize HP search config.
        features = self.job_config.get('feature_columns')
        target = self.job_config.get('target_column')

        if not features or not target:
            raise ValueError("feature_columns or target_column missing in HP search job config.")

        missing_cols = [c for c in features + [target] if c not in data.columns]
        if missing_cols:
            raise ValueError(f"Dataset is missing required columns for HP search: {missing_cols}")

        # Basic NaN handling - Objective function might need more sophisticated handling
        X = data[features].fillna(0)
        y = data[target]

        # Handle NaNs in target and ensure compatibility (similar to training handler)
        if y.isnull().any():
            logger.warning(f"Target column '{target}' contains NaN values. Dropping corresponding rows for HP search.")
            not_nan_mask = y.notna()
            X = X[not_nan_mask]
            y = y[not_nan_mask]
            if y.empty:
                raise ValueError("Target column resulted in empty Series after NaN removal during HP search preparation.")

        # Ensure y is numeric/boolean if needed by objective metric (e.g., F1 score)
        if pd.api.types.is_bool_dtype(y):
             y = y.astype(int)
        elif not pd.api.types.is_numeric_dtype(y):
             try: y = pd.to_numeric(y, errors='raise')
             except (ValueError, TypeError) as e:
                 raise TypeError(f"Target column '{target}' not numeric/boolean, unsuitable for default HP search objective: {e}") from e

        logger.info(f"Prepared HP search data: X={X.shape}, y={y.shape}")
        return X, y

    def _create_strategy(self) -> Optional[BaseModelStrategy]:
        """Strategy is created within the Objective for each trial, not upfront for the handler."""
        # However, we might need one later to train the final best model.
        # This method could potentially load info needed for the final training step.
        logger.debug("Strategy creation deferred to Objective/final training step for HP search.")
        return None
    
    def _create_optuna_sampler(self) -> Optional[optuna.samplers.BaseSampler]:
        """Creates Optuna sampler based on job config."""
        if not self.job_config: raise RuntimeError("Job config not loaded.")
        config = self.job_config.get('optuna_config', {})
        sampler_type_str = config.get('sampler_type') # Enum serialization handled by Pydantic
        sampler_params = config.get('sampler_config', {})
        seed = self.job_config.get('random_seed', 42)
        # Use the factory function
        return create_sampler(sampler_type_str, sampler_params, seed)

    def _create_optuna_pruner(self) -> Optional[optuna.pruners.BasePruner]:
        """Creates Optuna pruner based on job config."""
        if not self.job_config: raise RuntimeError("Job config not loaded.")
        config = self.job_config.get('optuna_config', {})
        pruner_type_str = config.get('pruner_type') # Enum serialization handled by Pydantic
        pruner_params = config.get('pruner_config', {})
        # Seed might not be applicable to all pruners, pass None if needed
        seed = self.job_config.get('random_seed', 42)
        # Use the factory function
        return create_pruner(pruner_type_str, pruner_params, seed) # Pass seed if needed by factory

    def _determine_optimization_direction(self) -> str:
        """Determine optimization direction based on the chosen objective metric."""
        # (Implementation remains the same)
        if not self.job_config: raise RuntimeError("Job config not loaded.")
        opt_config = self.job_config.get('optuna_config', {})
        # Default to F1 Weighted if not specified
        metric_name = opt_config.get('objective_metric', schemas.ObjectiveMetricEnum.F1_WEIGHTED.value)
        maximize_metrics = { m.value for m in schemas.ObjectiveMetricEnum } # Assume all defined metrics are maximized for now
        # TODO: Update this to reflect actual metrics and their directions
        # For now, assume all metrics are maximized
        if metric_name in maximize_metrics: return 'maximize'
        else: logger.warning(f"Metric '{metric_name}' not in maximize list. Defaulting to 'maximize'."); return 'maximize'


    def _execute_core_ml_task(self, prepared_data: Tuple[pd.DataFrame, pd.Series]) -> optuna.Study:
        """Executes the Optuna optimization study."""
        X, y = prepared_data
        optuna_storage_url = settings.OPTUNA_DB_URL
        storage = optuna.storages.RDBStorage(url=str(optuna_storage_url)) if optuna_storage_url else None
        study_name = self.job_db_record.optuna_study_name
        direction = self._determine_optimization_direction()
        if not study_name: raise ValueError("optuna_study_name is not defined.")
        sampler = self._create_optuna_sampler()
        pruner = self._create_optuna_pruner()
        logger.info(f"Creating/loading Optuna study: '{study_name}' Dir: '{direction}', Sampler: {sampler.__class__.__name__}, Pruner: {pruner.__class__.__name__}")
        try: study = optuna.create_study(study_name=study_name, storage=storage, load_if_exists=True, direction=direction, sampler=sampler, pruner=pruner)
        except Exception as study_err: logger.error(f"Failed to create/load study '{study_name}': {study_err}", exc_info=True); raise
        hp_space_config = self.job_config.get('hp_space', [])
        if not hp_space_config: raise ValueError("hp_space not defined.")
        try: objective = Objective(X, y, hp_space_config, self.job_config)
        except Exception as objective_err: logger.error(f"Failed to init Objective: {objective_err}", exc_info=True); raise
        optuna_config = self.job_config.get('optuna_config', {})

        n_trials = optuna_config.get('n_trials', 10)
        timeout = optuna_config.get('timeout_seconds') # Optional

        # Callback for progress update
        def progress_callback(study: optuna.Study, trial: optuna.trial.FrozenTrial):
            # Calculate progress based on completed/pruned/failed trials vs total requested
            # Use len(study.trials) as it includes all states except waiting
            completed_or_stopped_trials = len(study.trials)
            progress = 35 + int(60 * (completed_or_stopped_trials / n_trials)) if n_trials > 0 else 35
            self._update_progress(
                f"Running Optuna trial {trial.number+1}/{n_trials} (Current state: {trial.state.name})...",
                min(progress, 95) # Cap progress before final step
            )

        logger.info(f"Starting Optuna optimization for study '{study_name}', {n_trials} trials requested...")
        try:
            study.optimize(objective, n_trials=n_trials, timeout=timeout, callbacks=[progress_callback])
            logger.info(f"Optuna optimization finished for study '{study_name}'. State: {study.trials[-1].state if study.trials else 'N/A'}")
        except Exception as optimize_err:
             logger.error(f"Error during Optuna study optimize loop: {optimize_err}", exc_info=True)
             # Fail the job if optimize fails
             raise

        return study

    def _prepare_final_results(self, study: optuna.Study):
        """Processes Optuna results, trains/saves best model if configured."""
        logger.info(f"Processing results for Optuna study '{study.study_name}'...")
        self.final_db_results = {} # Reset results for this job run
        best_model_db_id: Optional[int] = None

        try:
            best_trial = study.best_trial
            logger.info(f"Best trial: #{best_trial.number}, Value={best_trial.value:.4f}, Params={best_trial.params}")
            self.final_db_results.update({
                'best_trial_id': best_trial.number,
                'best_params': best_trial.params,
                'best_value': best_trial.value
            })
        except ValueError:
            # This happens if no trials completed successfully
            completed_trials_count = len([t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE])
            total_trials_run = len(study.trials)
            logger.warning(f"Could not retrieve best trial (Completed: {completed_trials_count}/{total_trials_run}). Check trial logs.")
            self.final_db_results['status_message'] = f"HP search finished, but no best trial found ({completed_trials_count}/{total_trials_run} completed)."
            return

        # --- Train and Save Best Model (if configured) ---
        if self.job_config.get('save_best_model', True):
            logger.info("Training and saving best model...")

            # --- Re-parse job_config using the Pydantic model to ensure enums ---
            try:
                # job_config was loaded as dict initially, parse it now
                hp_search_config = schemas.HPSearchConfig.model_validate(self.job_config)
                model_type_enum = hp_search_config.model_type # Get the enum member
                model_name = hp_search_config.model_name # Get model name
            except Exception as config_parse_err:
                 logger.error(f"Failed to re-parse HPSearchConfig from job_config dict: {config_parse_err}", exc_info=True)
                 raise ValueError("Could not parse job configuration for final model training.") from config_parse_err
            # --- End Re-parse ---

            best_hyperparams = best_trial.params

            # --- Re-load/prepare data (inefficient but necessary if not stored) ---
            # TODO: Explore passing data via context or a more efficient mechanism
            session = self.current_session
            if not session: raise RuntimeError("DB Session lost.")
            raw_data = self._load_data(session)
            X, y = self._prepare_data(raw_data)
            # --- End Re-load ---

            try:
                # Pass the validated enum member
                final_strategy = create_model_strategy(model_type_enum, best_hyperparams, self.job_config)
                logger.info("Training final model with best parameters...")
                train_result = final_strategy.train(X, y)
                logger.info("Final model trained. Evaluation metrics: %s", train_result.metrics)

                # --- Save model record and artifact ---
                latest_version = model_db_service.find_latest_model_version(session, model_name)
                new_version = (latest_version or 0) + 1
                logger.info(f"Saving best model as '{model_name}' v{new_version}")

                model_data = {
                    'name': model_name,
                    'model_type': model_type_enum.value, # Store string value in DB
                    'version': new_version,
                    'description': f"Best model from HP Search Job {self.job_id} (Trial: {best_trial.number}, Value: {best_trial.value:.4f})",
                    'hyperparameters': best_hyperparams,
                    'performance_metrics': train_result.metrics,
                    'dataset_id': self.dataset_id,
                    'hp_search_job_id': self.job_id,
                    'training_job_id': None,
                    's3_artifact_path': None
                }
                new_model_id = model_db_service.create_model_record(session, model_data)
                s3_uri = f"s3://{settings.S3_BUCKET_NAME}/models/{model_name}/v{new_version}/model.pkl"
                save_success = final_strategy.save_model(s3_uri)

                if not save_success:
                    logger.error(f"Failed to save model artifact {s3_uri}. Rolling back.")
                    session.rollback()
                    self.final_db_results['status_message'] = f"HP search complete (Trial {best_trial.number}), but failed to save model artifact."
                    best_model_db_id = None
                else:
                    model_db_service.set_model_artifact_path(session, new_model_id, s3_uri)
                    best_model_db_id = new_model_id
                    logger.info(f"Best model artifact saved, DB record {new_model_id} updated.")
                    self.final_db_results['status_message'] = f"HP search completed. Best trial: {best_trial.number}. Model saved as ID: {best_model_db_id}."

            except Exception as final_train_err:
                 logger.error(f"Failed final model train/save: {final_train_err}", exc_info=True)
                 self.final_db_results['status_message'] = f"HP search complete (Trial {best_trial.number}), but failed final train/save: {final_train_err}"

        self.final_db_results['best_ml_model_id'] = best_model_db_id
        # If no specific error message set, use default success
        if 'status_message' not in self.final_db_results:
             self.final_db_results['status_message'] = f"HP search completed successfully. Best trial: {best_trial.number}."