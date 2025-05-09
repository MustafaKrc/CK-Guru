# worker/ml/services/strategies/sklearn_strategy.py
import logging
from typing import Any, Dict
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
# Import other sklearn models or components as needed

from .base_strategy import BaseModelStrategy, TrainResult
from shared.schemas.enums import ModelTypeEnum

logger = logging.getLogger(__name__)

class SklearnStrategy(BaseModelStrategy):
    """Execution strategy for scikit-learn based models."""

    def __init__(self, model_type: ModelTypeEnum, model_config: Dict, job_config: Dict):
        """Store the specific model type enum member."""
        self.model_type_enum = model_type # Store the enum member
        super().__init__(model_config, job_config)

    def _initialize_model_internals(self):
        """No specific sklearn initialization needed post __init__."""
        pass

    def _get_model_instance(self) -> Any:
        """Creates the specific scikit-learn model instance based on stored enum."""
        hyperparams = self.model_config # Direct hyperparameters for this instance
        random_state = self.job_config.get('random_seed', 42)

        # Compare against the stored enum member
        if self.model_type_enum == ModelTypeEnum.SKLEARN_RANDOMFOREST:
            # Filter hyperparameters to only those accepted by the model
            valid_params = {k: v for k, v in hyperparams.items() if k in RandomForestClassifier().get_params()}
            model = RandomForestClassifier(**valid_params, random_state=random_state)
        # elif self.model_type_enum == ModelTypeEnum.SKLEARN_LOGISTICREGRESSION:
        #     from sklearn.linear_model import LogisticRegression
        #     valid_params = {k: v for k, v in hyperparams.items() if k in LogisticRegression().get_params()}
        #     model = LogisticRegression(**valid_params, random_state=random_state)
        else:
            # Use the enum's value for the error message
            raise ValueError(f"Unsupported scikit-learn model type in SklearnStrategy: {self.model_type_enum.value}")

        logger.info(f"Initialized sklearn model: {model.__class__.__name__} with params: {model.get_params()}")
        return model

    def train(self, X: pd.DataFrame, y: pd.Series) -> TrainResult:
        """Trains a scikit-learn model with train/test split evaluation."""
        logger.info(f"SklearnStrategy: Starting training for model type: {self.model_type_enum.value}")
        logger.info(f"Training data shape: X={X.shape}, y={y.shape}")

        # --- Data Splitting ---
        test_size = self.job_config.get('eval_test_split_size', 0.2)
        random_state = self.job_config.get('random_seed', 42)

        if test_size > 0.0 and test_size < 1.0:
            try:
                # Ensure y is suitable for stratification (e.g., integer class labels)
                stratify_col = y if pd.api.types.is_integer_dtype(y) or pd.api.types.is_bool_dtype(y) else None
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=test_size, random_state=random_state, stratify=stratify_col
                )
                logger.info(f"Data split: Train={X_train.shape}, Test={X_test.shape}")
            except Exception as e:
                 logger.warning(f"Stratified split failed ({e}). Falling back to non-stratified split.", exc_info=False)
                 X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=test_size, random_state=random_state
                 )
        else:
            logger.warning("Test size is 0 or >= 1. Training on full dataset without evaluation split.")
            X_train, X_test, y_train, y_test = X, pd.DataFrame(), y, pd.Series() # Assign empty test set

        # --- Model Initialization & Training ---
        try:
            self.model = self._get_model_instance() # Instantiate the model
            logger.info(f"Fitting {self.model.__class__.__name__}...")
            self.model.fit(X_train, y_train)
            logger.info("Model fitting complete.")
        except Exception as e:
            logger.error(f"Error during model fitting: {e}", exc_info=True)
            raise # Propagate error to fail the job

        # --- Evaluation ---
        metrics = {}
        if not X_test.empty:
             logger.info("Evaluating sklearn model on test set...")
             metrics = self.evaluate(X_test, y_test) # Use base class evaluate
        else:
             logger.warning("No test set available for evaluation during training.")
             # Optionally evaluate on training set (use cautiously)
             # metrics = self.evaluate(X_train, y_train)
             # metrics = {f"train_{k}": v for k,v in metrics.items()} # Rename to avoid confusion

        return TrainResult(model=self.model, metrics=metrics)

    def predict(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Generates predictions for each row using the fitted sklearn model.
        Returns predictions and probabilities as lists.
        """
        if self.model is None:
            raise RuntimeError("Sklearn model is not fitted or loaded. Cannot predict.")

        # data is potentially multi-row here
        logger.info(f"SklearnStrategy: Generating predictions for {len(data)} samples...")
        try:
            # .predict() returns a numpy array
            predictions_array = self.model.predict(data)
            # Convert numpy array to list for JSON serialization
            predictions_list = predictions_array.tolist()
            result = {'predictions': predictions_list}

            # Add probabilities if the model supports it
            if hasattr(self.model, 'predict_proba'):
                 # .predict_proba() returns numpy array of shape (n_samples, n_classes)
                 probabilities_array = self.model.predict_proba(data)
                 # Convert numpy array to list of lists for JSON serialization
                 probabilities_list = probabilities_array.tolist()
                 result['probabilities'] = probabilities_list

            return result
        except Exception as e:
            logger.error(f"Error during sklearn prediction: {e}", exc_info=True)
            raise # Re-raise the exception