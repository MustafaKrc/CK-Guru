# worker/ml/services/strategies/base_strategy.py
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, NamedTuple
import pandas as pd

# Import artifact service singleton
from ..artifact_service import artifact_service

logger = logging.getLogger(__name__)

# Define a structure for training results
class TrainResult(NamedTuple):
    model: Any
    metrics: Dict[str, float]

class BaseModelStrategy(ABC):
    """Abstract base class for model-specific execution strategies."""

    def __init__(self, model_config: Dict, job_config: Dict):
        """
        Initializes the strategy.

        Args:
            model_config: Hyperparameters and settings for the specific model instance.
            job_config: Overall job configuration (seed, evaluation settings, etc.).
        """
        self.model_config = model_config
        self.job_config = job_config
        self.model: Any = None # Holds the actual model object (e.g., sklearn classifier)
        self._initialize_model_internals()
        logger.debug(f"Initialized strategy: {self.__class__.__name__}")

    def _initialize_model_internals(self):
        """Optional hook for subclasses to initialize specific things after base __init__."""
        pass

    def get_hyperparameter_space(self) -> set:
        """
        Introspect the real model class __init__ signature
        to list accepted hyperparameter names.
        """
        from inspect import signature, Parameter
        # Instantiate unfitted model to get its class
        model = self._get_model_instance()
        init_sig = signature(type(model).__init__)
        return {
            name
            for name, param in init_sig.parameters.items()
            if name not in ('self', 'args', 'kwargs')
               and param.kind in (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY)
        }

    @abstractmethod
    def _get_model_instance(self) -> Any:
        """
        Abstract method for subclasses to implement the instantiation
        of their specific underlying ML model object using stored config.
        This should return an *unfitted* model instance.
        """
        pass

    @abstractmethod
    def train(self, X: pd.DataFrame, y: pd.Series) -> TrainResult:
        """
        Abstract method responsible for the entire training process for this strategy.
        Should include:
        1. Instantiating the model (e.g., using _get_model_instance).
        2. Performing any necessary data splitting (train/test or CV setup).
        3. Fitting the model.
        4. Evaluating the model.
        5. Returning a TrainResult tuple.
        """
        pass

    @abstractmethod
    def predict(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Abstract method for generating predictions.

        Args:
            data: Input features DataFrame.

        Returns:
            Dictionary containing predictions, potentially including probabilities.
            Example: {'predictions': [0, 1, 0], 'probabilities': [[0.9, 0.1], ...]}
        """
        pass

    def evaluate(self, X_test: pd.DataFrame, y_test: pd.Series) -> Dict[str, float]:
        """
        Default evaluation logic using the fitted model.
        Calculates accuracy and weighted F1-score. Can be overridden.
        """
        if self.model is None:
            raise RuntimeError("Model is not available for evaluation. Ensure it's trained or loaded.")

        logger.info(f"Evaluating model {self.model.__class__.__name__}...")
        try:
            # Ensure predict method exists
            if not hasattr(self.model, 'predict'):
                 raise TypeError(f"Model object {type(self.model)} lacks a 'predict' method.")

            y_pred = self.model.predict(X_test)

            # Import necessary metrics locally within the method
            from sklearn.metrics import accuracy_score, f1_score

            # Ensure y_test is compatible (e.g., convert to int if needed)
            y_test_eval = pd.to_numeric(y_test, errors='coerce').fillna(-1).astype(int)
            y_pred_eval = pd.to_numeric(pd.Series(y_pred), errors='coerce').fillna(-1).astype(int)

            # Handle cases where conversion might fail or result in incompatible types/values
            # This might require more robust checking based on expected target types

            accuracy = accuracy_score(y_test_eval, y_pred_eval)
            # Ensure pos_label is appropriate or handle binary/multiclass explicitly
            # Using weighted average is generally safer for potential imbalance
            f1 = f1_score(y_test_eval, y_pred_eval, average='weighted', zero_division=0)

            logger.info(f"Evaluation Metrics - Accuracy: {accuracy:.4f}, F1 (weighted): {f1:.4f}")
            return {"accuracy": accuracy, "f1_weighted": f1}
        except Exception as e:
            logger.error(f"Error during model evaluation: {e}", exc_info=True)
            # Return default metrics indicating failure
            return {"accuracy": 0.0, "f1_weighted": 0.0}

    def load_model(self, artifact_path: str):
        """Loads the model object using the artifact service."""
        logger.info(f"Strategy {self.__class__.__name__}: Loading model from {artifact_path}")
        self.model = artifact_service.load_artifact(artifact_path)
        if self.model is None:
            raise IOError(f"Failed to load model from artifact path: {artifact_path}")
        logger.info(f"Model {self.model.__class__.__name__} loaded successfully.")

    def save_model(self, artifact_path: str) -> bool:
        """Saves the model object using the artifact service."""
        if self.model is None:
            logger.error("Cannot save model: Internal model object is None.")
            return False
        logger.info(f"Strategy {self.__class__.__name__}: Saving model to {artifact_path}")
        return artifact_service.save_artifact(self.model, artifact_path)