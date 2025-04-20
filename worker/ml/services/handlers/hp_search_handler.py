# worker/ml/services/handlers/hp_search_handler.py
import logging
from typing import Any, Tuple, Dict, Optional
import pandas as pd

import optuna

from services.factories.strategy_factory import create_model_strategy

from .base_handler import BaseMLJobHandler
from ..strategies.base_strategy import BaseModelStrategy, TrainResult
from shared.db.models import HyperparameterSearchJob, MLModel, JobStatusEnum # Import specific job model
from shared.core.config import settings
from .. import model_db_service, job_db_service
from ..hp_search_objective import Objective # Import the objective class
from ..factories.optuna_factory import create_sampler, create_pruner


from shared import schemas

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
        config = self.job_config.get('optuna_config', {})
        sampler_type_str = config.get('sampler_type') # Enum serialization handled by Pydantic
        sampler_params = config.get('sampler_config', {})
        seed = self.job_config.get('random_seed', 42)
        # Use the factory function
        return create_sampler(sampler_type_str, sampler_params, seed)

    def _create_optuna_pruner(self) -> Optional[optuna.pruners.BasePruner]:
        """Creates Optuna pruner based on job config."""
        config = self.job_config.get('optuna_config', {})
        pruner_type_str = config.get('pruner_type') # Enum serialization handled by Pydantic
        pruner_params = config.get('pruner_config', {})
        # Seed might not be applicable to all pruners, pass None if needed
        seed = self.job_config.get('random_seed', 42)
        # Use the factory function
        return create_pruner(pruner_type_str, pruner_params, seed) # Pass seed if needed by factory

    def _determine_optimization_direction(self) -> str:
        """Determine optimization direction based on the chosen objective metric."""
        opt_config = self.job_config.get('optuna_config', {})
        # Default to F1 Weighted if not specified
        metric_name = opt_config.get('objective_metric', schemas.ObjectiveMetricEnum.F1_WEIGHTED.value)

        # Define metrics that should be maximized
        maximize_metrics = {
            schemas.ObjectiveMetricEnum.F1_WEIGHTED.value,
            schemas.ObjectiveMetricEnum.AUC.value,
            schemas.ObjectiveMetricEnum.PRECISION_WEIGHTED.value,
            schemas.ObjectiveMetricEnum.RECALL_WEIGHTED.value,
            schemas.ObjectiveMetricEnum.ACCURACY.value
        }
        # Add metrics to minimize here if needed
        # minimize_metrics = {'log_loss', 'mae', 'rmse'}

        if metric_name in maximize_metrics:
            return 'maximize'
        # elif metric_name in minimize_metrics:
        #     return 'minimize'
        else:
            logger.warning(f"Could not determine optimization direction for metric '{metric_name}'. Defaulting to 'maximize'.")
            return 'maximize'


    def _execute_core_ml_task(self, prepared_data: Tuple[pd.DataFrame, pd.Series]) -> optuna.Study:
        """Executes the Optuna optimization study."""
        X, y = prepared_data
        optuna_storage_url = settings.OPTUNA_DB_URL
        storage = optuna.storages.RDBStorage(url=optuna_storage_url) if optuna_storage_url else None
        study_name = self.job_db_record.optuna_study_name
        optuna_config = self.job_config.get('optuna_config', {})
        direction = optuna_config.get('direction', 'maximize') # Default to maximize

        if not study_name:
             raise ValueError("optuna_study_name is not defined in the job record.")
        
        # --- Create Sampler and Pruner ---
        sampler = self._create_optuna_sampler()
        pruner = self._create_optuna_pruner()

        logger.info(
            f"Creating/loading Optuna study: '{study_name}' "
            f"Direction: '{direction}', "
            f"Sampler: {sampler.__class__.__name__ if sampler else 'Default'}, "
            f"Pruner: {pruner.__class__.__name__ if pruner else 'Default'}"
        )

        try:
            study = optuna.create_study(
                study_name=study_name,
                storage=storage,
                load_if_exists=True, # Let Optuna handle resuming based on name/storage
                direction=direction,
                sampler=sampler,
                pruner=pruner
            )
        except Exception as study_err:
             logger.error(f"Failed to create or load Optuna study '{study_name}': {study_err}", exc_info=True)
             raise

        hp_space_config = self.job_config.get('hp_space', [])
        if not hp_space_config:
            raise ValueError("hp_space not defined in HP search job config.")

        # Instantiate the objective function
        try:
            objective = Objective(X, y, hp_space_config, self.job_config)
        except Exception as objective_err:
             logger.error(f"Failed to initialize Objective function: {objective_err}", exc_info=True)
             raise

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
            logger.info(f"Best trial found: Number={best_trial.number}, Value={best_trial.value:.4f}, Params={best_trial.params}")
            self.final_db_results['best_trial_id'] = best_trial.number
            self.final_db_results['best_params'] = best_trial.params
            self.final_db_results['best_value'] = best_trial.value
        except ValueError:
            # This happens if no trials completed successfully
            completed_trials_count = len([t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE])
            total_trials_run = len(study.trials)
            logger.warning(f"Could not retrieve best trial (Completed: {completed_trials_count}/{total_trials_run}). Check individual trial logs.")
            self.final_db_results['status_message'] = f"HP search finished, but could not determine a best trial ({completed_trials_count}/{total_trials_run} completed)."
            # Mark job as failed if no trials completed? Or success with warning? Let's use a warning message.
            # The overall job status might be set later based on this message.
            return # Exit early if no best trial

        # --- Train and Save Best Model (if configured and best_trial exists) ---
        if self.job_config.get('save_best_model', True):
            logger.info("Training and saving best model from HP search...")
            model_type = self.job_config.get('model_type')
            best_hyperparams = best_trial.params

            # --- Re-load/prepare data (inefficient but necessary if not stored) ---
            # TODO: Explore passing data via context or a more efficient mechanism
            session = self.current_session
            if not session: raise RuntimeError("DB Session lost before final model training.")
            raw_data = self._load_data(session)
            X, y = self._prepare_data(raw_data)
            # --- End Re-load ---

            try:
                # Create strategy with best params
                final_strategy = create_model_strategy(model_type, best_hyperparams, self.job_config)
                # Train the final model on the full dataset X, y
                logger.info("Training final model with best parameters...")
                # We call train here, assuming it handles fitting. If evaluate needed, adjust.
                train_result = final_strategy.train(X, y) # Re-train on full data
                logger.info("Final model trained. Evaluation metrics (on split): %s", train_result.metrics)

                # --- Save model record and artifact ---
                model_name = self.job_config.get('model_name', f'hp_search_{self.job_id}_best') # Default name
                latest_version = model_db_service.find_latest_model_version(session, model_name)
                new_version = (latest_version or 0) + 1
                logger.info(f"Saving best model as '{model_name}' v{new_version}")

                model_data = {
                    'name': model_name, 'model_type': model_type, 'version': new_version,
                    'description': f"Best model from HP Search Job {self.job_id} (Study: {study.study_name}, Trial: {best_trial.number})",
                    'hyperparameters': best_hyperparams,
                    'performance_metrics': train_result.metrics, # Use metrics from final training run
                    'dataset_id': self.dataset_id,
                    'hp_search_job_id': self.job_id, # Link back to this HP search job
                    'training_job_id': None,
                    's3_artifact_path': None
                }

                # Use service to create record
                new_model_id = model_db_service.create_model_record(session, model_data)

                # Define artifact path
                s3_uri = f"s3://{settings.S3_BUCKET_NAME}/models/{model_name}/v{new_version}/model.pkl"
                save_success = final_strategy.save_model(s3_uri)

                if not save_success:
                    logger.error(f"Failed to save best model artifact to {s3_uri}. Rolling back DB changes.")
                    session.rollback()
                    # Set status message for final DB update, but don't raise here to allow job status update
                    self.final_db_results['status_message'] = f"HP search complete, but failed to save best model artifact."
                else:
                    model_db_service.set_model_artifact_path(session, new_model_id, s3_uri)
                    best_model_db_id = new_model_id
                    logger.info(f"Best model artifact saved and DB record {new_model_id} updated.")

            except Exception as final_train_err:
                 logger.error(f"Failed to train or save the best model: {final_train_err}", exc_info=True)
                 # Don't raise, but update status message
                 self.final_db_results['status_message'] = f"HP search complete, but failed during final model training/saving: {final_train_err}"
                 # Don't rollback here, let the main handler manage the session commit/rollback based on overall success

        # Store the best model ID (if saved) in the final results
        self.final_db_results['best_ml_model_id'] = best_model_db_id
        # If no specific error message set, use default success
        if 'status_message' not in self.final_db_results:
             self.final_db_results['status_message'] = f"HP search completed. Best trial: {best_trial.number}."