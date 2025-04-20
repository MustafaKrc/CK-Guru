# worker/ml/services/handlers/hp_search_handler.py
import logging
from typing import Any, Tuple, Dict, Optional
import pandas as pd

import optuna

from services.factories.strategy_factory import create_model_strategy

from .base_handler import BaseMLJobHandler
from ..strategies.base_strategy import BaseModelStrategy, TrainResult
from shared.db.models import HyperparameterSearchJob, MLModel # Import specific job model
from shared.core.config import settings
from .. import model_db_service, job_db_service
from ..hp_search_objective import Objective # Import the objective class

logger = logging.getLogger(__name__)

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

        logger.info(f"Creating/loading Optuna study: '{study_name}' with direction '{direction}'")
        study = optuna.create_study(
            study_name=study_name,
            storage=storage,
            load_if_exists=True, # Allows resuming or adding trials
            direction=direction
            # TODO: Add sampler/pruner configuration later based on optuna_config
        )

        hp_space_config = self.job_config.get('hp_space', [])
        if not hp_space_config:
            raise ValueError("hp_space not defined in HP search job config.")

        # Instantiate the objective function
        objective = Objective(X, y, hp_space_config, self.job_config)

        n_trials = optuna_config.get('n_trials', 10)
        timeout = optuna_config.get('timeout_seconds') # Optional

        # Callback for progress update
        def progress_callback(study: optuna.Study, trial: optuna.trial.FrozenTrial):
             # Calculate progress based on completed trials vs total requested
             # Note: n_trials might not be reached if timeout occurs
             completed_trials = len([t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE])
             progress = 35 + int(60 * (completed_trials / n_trials)) if n_trials > 0 else 35
             self._update_progress(f"Running Optuna trial {trial.number+1}/{n_trials} (Completed: {completed_trials})...", min(progress, 95)) # Cap progress before final step

        logger.info(f"Starting Optuna optimization for study '{study_name}', {n_trials} trials requested...")
        study.optimize(objective, n_trials=n_trials, timeout=timeout, callbacks=[progress_callback])
        logger.info(f"Optuna optimization complete for study '{study_name}'.")

        return study

    def _prepare_final_results(self, study: optuna.Study):
        """Processes Optuna results, trains/saves best model if configured."""
        logger.info(f"Processing results for Optuna study '{study.study_name}'...")
        self.final_db_results = {} # Reset results for this job run
        best_model_db_id: Optional[int] = None

        completed_trials = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
        if not completed_trials:
            logger.warning("No completed trials found in the Optuna study.")
            self.final_db_results['status_message'] = "HP search finished, but no trials completed successfully."
            # Job status will likely remain FAILED or be set based on this message
            return

        try:
            best_trial = study.best_trial
            logger.info(f"Best trial found: Number={best_trial.number}, Value={best_trial.value:.4f}, Params={best_trial.params}")
            self.final_db_results['best_trial_id'] = best_trial.number
            self.final_db_results['best_params'] = best_trial.params
            self.final_db_results['best_value'] = best_trial.value
        except ValueError:
             logger.warning("Could not retrieve best trial (e.g., study had only pruned/failed trials).")
             self.final_db_results['status_message'] = "HP search finished, but could not determine a best trial."
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
                new_model_id = model_db_service.create_model_record(session, model_data)

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

        self.final_db_results['best_ml_model_id'] = best_model_db_id
        # If no specific error message set, use default success
        if 'status_message' not in self.final_db_results:
             self.final_db_results['status_message'] = f"HP search completed. Best trial: {best_trial.number}."