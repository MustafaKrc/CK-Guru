# worker/ml/services/handlers/training_handler.py
import logging
from typing import Any, Tuple, Dict
import pandas as pd

from services.factories.strategy_factory import create_model_strategy

from .base_handler import BaseMLJobHandler
from ..strategies.base_strategy import BaseModelStrategy, TrainResult
from shared.db.models import TrainingJob, MLModel # Import specific job model
from shared.core.config import settings
from .. import model_db_service # Import necessary db services

logger = logging.getLogger(__name__)

class TrainingJobHandler(BaseMLJobHandler):
    """Handles the execution of model training jobs."""

    @property
    def job_type_name(self) -> str:
        return 'TrainingJob'

    @property
    def job_model_class(self) -> type:
        return TrainingJob

    def _prepare_data(self, data: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepares features (X) and target (y) for training."""
        logger.info("Preparing data for training...")
        features = self.job_config.get('feature_columns', [])
        target = self.job_config.get('target_column')
        if not features or not target:
            raise ValueError("feature_columns or target_column missing in training job config.")

        missing_cols = [c for c in features + [target] if c not in data.columns]
        if missing_cols:
            raise ValueError(f"Dataset is missing required columns for training: {missing_cols}")

        # Basic NaN handling for features - consider more sophisticated imputation
        X = data[features].fillna(0)
        y = data[target]

        # Handle NaNs in target and ensure compatibility
        if y.isnull().any():
            logger.warning(f"Target column '{target}' contains NaN values. Dropping corresponding rows.")
            not_nan_mask = y.notna()
            X = X[not_nan_mask]
            y = y[not_nan_mask]
            if y.empty:
                raise ValueError("Target column resulted in empty Series after NaN removal.")

        # Example: Convert boolean target to int if needed by model
        if pd.api.types.is_bool_dtype(y):
             y = y.astype(int)
        elif not pd.api.types.is_numeric_dtype(y):
            # Attempt conversion or raise error if target is non-numeric and unsuitable
            try:
                y = pd.to_numeric(y, errors='raise') # Raise error if conversion fails
            except (ValueError, TypeError) as e:
                raise TypeError(f"Target column '{target}' is not numeric or boolean and cannot be used directly for training: {e}") from e

        logger.info(f"Prepared training data: X={X.shape}, y={y.shape}")
        return X, y

    def _create_strategy(self) -> BaseModelStrategy:
        """Creates the specific model strategy based on job config."""
        model_type = self.job_config.get('model_type')
        hyperparams = self.job_config.get('hyperparameters', {})
        if not model_type:
            raise ValueError("model_type not specified in training job config.")

        # Use the factory from the base handler or imported directly
        strategy = create_model_strategy(model_type, hyperparams, self.job_config)

        # --- Validate that only known hyperparameters were passed ---
        provided = self.job_config.get("hyperparameters", {}) or {}
        allowed = strategy.get_hyperparameter_space()  # already a set
        unknown = set(provided) - allowed

        if unknown:
            logger.error(f"Unknown hyperparameters for '{model_type}': {unknown}")
            raise ValueError(f"Unknown hyperparameters: {sorted(unknown)}")

        return strategy

    def _execute_core_ml_task(self, prepared_data: Tuple[pd.DataFrame, pd.Series]) -> TrainResult:
        """Executes the training using the selected strategy."""
        X, y = prepared_data
        if self.model_strategy is None:
            raise RuntimeError("Model strategy was not created.")

        logger.info(f"Executing training via strategy: {self.model_strategy.__class__.__name__}")
        train_result = self.model_strategy.train(X, y)
        logger.info("Training execution complete. Metrics: %s", train_result.metrics)
        return train_result

    def _prepare_final_results(self, ml_result: TrainResult):
        """Saves the trained model artifact and creates the MLModel DB record."""
        logger.info("Saving training results (model artifact and DB record)...")
        model_name = self.job_config.get('model_name')
        model_type = self.job_config.get('model_type')
        hyperparams = self.job_config.get('hyperparameters', {})
        if not model_name:
            raise ValueError("model_name missing in training job config.")

        # Use the session stored by the base handler's run_job method
        session = self.current_session
        if not session:
            raise RuntimeError("DB Session not available in _prepare_final_results")

        # --- Create Model Record ---
        latest_version = model_db_service.find_latest_model_version(session, model_name)
        new_version = (latest_version or 0) + 1
        logger.info(f"Determined next version for model '{model_name}': v{new_version}")

        model_data = {
            'name': model_name, 'model_type': model_type, 'version': new_version,
            'description': f"Trained via TrainingJob {self.job_id}",
            'hyperparameters': hyperparams,
            'performance_metrics': ml_result.metrics,
            'dataset_id': self.dataset_id,
            'training_job_id': self.job_id, # Link back to this job
            'hp_search_job_id': None, # Not from HP search
            's3_artifact_path': None # Set after saving
        }
        new_model_id = model_db_service.create_model_record(session, model_data)

        # --- Save Artifact ---
        s3_uri = f"s3://{settings.S3_BUCKET_NAME}/models/{model_name}/v{new_version}/model.pkl" # Standardize name
        logger.info(f"Attempting to save model artifact to {s3_uri}")
        save_success = self.model_strategy.save_model(s3_uri) # Use strategy to save model

        if not save_success:
            # IMPORTANT: Rollback DB changes if artifact save fails
            logger.error(f"Failed to save model artifact to {s3_uri}. Rolling back model DB record creation.")
            session.rollback()
            raise IOError(f"Failed to save model artifact to {s3_uri}")

        # --- Update Model Record with Path ---
        model_db_service.set_model_artifact_path(session, new_model_id, s3_uri)
        logger.info(f"Model artifact saved and DB record {new_model_id} updated with path.")

        # Populate final_db_results for the final job update
        self.final_db_results['ml_model_id'] = new_model_id
        self.final_db_results['status_message'] = f"Training successful. Model ID: {new_model_id}."