# worker/ml/services/training_service.py
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, NamedTuple, Tuple, Optional

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier # Example model
from sklearn.metrics import accuracy_score, f1_score # Example metrics
# Import other sklearn components as needed

from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper()) # Assuming settings is available or imported

class TrainResult(NamedTuple):
    """Structure to hold training results."""
    model: Any
    metrics: Dict[str, float]
    # Add other relevant results like scaler objects, feature names etc. if needed

class BaseModelTrainer(ABC):
    """Abstract base class for model trainers."""

    def __init__(self, model_config: Dict[str, Any], job_config: Dict[str, Any]):
        """
        Initialize the trainer.

        Args:
            model_config: Hyperparameters and settings specific to the model instance.
            job_config: Overall job configuration (might include eval strategy, seed, etc.).
        """
        self.model_config = model_config
        self.job_config = job_config
        self.model = None # Placeholder for the trained model object

    @abstractmethod
    def train(self, X: pd.DataFrame, y: pd.Series) -> TrainResult:
        """
        Trains the model on the provided data.

        Args:
            X: DataFrame of features.
            y: Series of target labels.

        Returns:
            A TrainResult named tuple containing the trained model object
            and a dictionary of performance metrics.
        """
        pass

    def evaluate(self, X_test: pd.DataFrame, y_test: pd.Series) -> Dict[str, float]:
        """
        Evaluates the trained model on test data.
        (Can be overridden by subclasses if specific evaluation is needed)

        Args:
            X_test: Test features.
            y_test: Test labels.

        Returns:
            Dictionary of performance metrics.
        """
        if self.model is None:
            raise RuntimeError("Model has not been trained yet. Call train() first.")
        try:
            y_pred = self.model.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)
            f1 = f1_score(y_test, y_pred, average='weighted') # Use weighted for multiclass/imbalanced
            logger.info(f"Evaluation Metrics - Accuracy: {accuracy:.4f}, F1 (weighted): {f1:.4f}")
            return {"accuracy": accuracy, "f1_weighted": f1}
        except Exception as e:
            logger.error(f"Error during model evaluation: {e}", exc_info=True)
            return {"accuracy": 0.0, "f1_weighted": 0.0} # Return default metrics on error


# --- Concrete Scikit-learn Trainer ---
class SklearnTrainer(BaseModelTrainer):
    """Trainer for scikit-learn compatible models."""

    def _init_model(self):
        """Initializes the scikit-learn model based on config."""
        model_type = self.job_config.get('model_type', 'sklearn_randomforest') # Get from overall config
        hyperparams = self.model_config # Hyperparams are passed directly

        # Example: Add more model types here
        if model_type == 'sklearn_randomforest':
            # Extract known hyperparameters for RandomForestClassifier, pass others **kwargs style
            known_params = {k: v for k, v in hyperparams.items() if k in RandomForestClassifier()._get_param_names()}
            # Add default random_state if not provided for reproducibility
            if 'random_state' not in known_params:
                 known_params['random_state'] = self.job_config.get('random_seed', 42)
            logger.info(f"Initializing RandomForestClassifier with params: {known_params}")
            return RandomForestClassifier(**known_params)
        # elif model_type == 'sklearn_logreg':
        #     # return LogisticRegression(**hyperparams)
        #     pass
        else:
            raise ValueError(f"Unsupported scikit-learn model type: {model_type}")


    def train(self, X: pd.DataFrame, y: pd.Series) -> TrainResult:
        """Trains a scikit-learn model."""
        logger.info(f"Starting training for model type: {self.job_config.get('model_type')}")
        logger.info(f"Training data shape: X={X.shape}, y={y.shape}")

        # --- Data Preprocessing (Example: Train/Test Split) ---
        # This could be more sophisticated (e.g., cross-validation) based on job_config
        test_size = self.job_config.get('eval_test_split_size', 0.2)
        random_seed = self.job_config.get('random_seed', 42)

        try:
            # Ensure y is numeric/boolean for stratification if needed
            y_numeric = pd.to_numeric(y, errors='coerce').fillna(0).astype(int)

            X_train, X_test, y_train, y_test = train_test_split(
                X, y_numeric, test_size=test_size, random_state=random_seed, stratify=y_numeric # Stratify if classification
            )
            logger.info(f"Data split: Train={X_train.shape}, Test={X_test.shape}")
        except Exception as e:
             logger.error(f"Error during train/test split: {e}. Using full dataset for training.", exc_info=True)
             # Fallback: Train on full data if split fails (less ideal)
             X_train, X_test, y_train, y_test = X, pd.DataFrame(), y_numeric, pd.Series()


        # --- Model Initialization ---
        try:
            self.model = self._init_model()
        except Exception as e:
            logger.error(f"Failed to initialize model: {e}", exc_info=True)
            raise # Propagate error to fail the task

        # --- Model Training ---
        try:
            logger.info("Fitting model...")
            self.model.fit(X_train, y_train)
            logger.info("Model fitting complete.")
        except Exception as e:
            logger.error(f"Error during model fitting: {e}", exc_info=True)
            raise # Propagate error

        # --- Evaluation (Optional) ---
        metrics = {}
        if not X_test.empty:
             logger.info("Evaluating model on test set...")
             metrics = self.evaluate(X_test, y_test)
        else:
             logger.warning("No test set available for evaluation.")
             # Optionally evaluate on training set (can lead to overfitting metric)
             # metrics = self.evaluate(X_train, y_train) # Use with caution

        return TrainResult(model=self.model, metrics=metrics)


# --- Factory Function (Optional but Recommended) ---
def get_trainer(model_type: str, model_config: Dict[str, Any], job_config: Dict[str, Any]) -> BaseModelTrainer:
    """Factory function to get the appropriate trainer instance."""
    if model_type.startswith('sklearn_'):
        return SklearnTrainer(model_config, job_config)
    # elif model_type.startswith('pytorch_'):
    #     # return PyTorchTrainer(model_config, job_config) # Implement later
    #     raise NotImplementedError(f"Trainer for {model_type} not yet implemented.")
    else:
        raise ValueError(f"Unsupported model type for trainer factory: {model_type}")

# Example usage (within the Celery task):
# config = # ... load job config ...
# model_config = config.get('hyperparameters', {})
# model_type = config.get('model_type')
# trainer = get_trainer(model_type, model_config, config)
# result = trainer.train(X_data, y_data)
# trained_model = result.model
# performance_metrics = result.metrics