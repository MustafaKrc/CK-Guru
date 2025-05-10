# worker/ml/services/strategies/base_strategy.py
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, NamedTuple, Set, Type
import pandas as pd
from inspect import signature, Parameter

from services.interfaces import IArtifactService

from sklearn.metrics import accuracy_score, f1_score 


logger = logging.getLogger(__name__)

# Define a structure for training results
class TrainResult(NamedTuple):
    model: Any
    metrics: Dict[str, float]

class BaseModelStrategy(ABC):
    """Abstract base class for model-specific execution strategies."""

    def __init__(
        self,
        model_config: Dict,
        job_config: Dict,
        artifact_service: IArtifactService 
    ):
        """
        Initializes the strategy with configs and artifact service.

        Args:
            model_config: Hyperparameters for the model instance.
            job_config: Overall job configuration.
            artifact_service: Injected instance for loading/saving models.
        """
        self.model_config = model_config
        self.job_config = job_config
        self.artifact_service: IArtifactService = artifact_service #
        self.model: Any = None # Holds the actual model object
        self._initialize_model_internals()
        logger.debug(f"Initialized strategy: {self.__class__.__name__}")

    def _initialize_model_internals(self):
        """Optional hook for subclasses to initialize specific things after base __init__."""
        pass

    def get_hyperparameter_space(self) -> Set[str]:
        """
        Return the names of ctor arguments that look like
        real hyper‑parameters (i.e. exclude *args/**kwargs, 'self', etc.).
        Works for scikit‑learn and most other Python ML libraries.
        """
        model_cls = self._get_model_class()
        sig = signature(model_cls.__init__)

        hp_names = {
            name
            for name, param in sig.parameters.items()
            if name != "self"
            and param.kind
            in (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY)
        }
        return hp_names
        
    @abstractmethod
    def _get_model_class(self) -> Type:
        """Return the *class* (not instance) of the underlying ML model."""
        pass

    @abstractmethod
    def _get_model_instance(self) -> Any:
        """Subclasses implement to instantiate their specific ML model."""
        pass

    @abstractmethod
    def train(self, X: pd.DataFrame, y: pd.Series) -> TrainResult:
        """Subclasses implement the training process."""
        pass

    @abstractmethod
    def predict(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Subclasses implement prediction."""
        pass

    def evaluate(self, X_test: pd.DataFrame, y_test: pd.Series) -> Dict[str, float]:
        """Default evaluation logic (remains the same)."""
        if self.model is None: raise RuntimeError("Model not available for evaluation.")
        logger.info(f"Evaluating model {self.model.__class__.__name__}...")
        try:
            if not hasattr(self.model, 'predict'): raise TypeError("Model lacks 'predict'.")
            y_pred = self.model.predict(X_test)
            y_test_eval = pd.to_numeric(y_test, errors='coerce').fillna(-1).astype(int)
            y_pred_eval = pd.to_numeric(pd.Series(y_pred), errors='coerce').fillna(-1).astype(int)
            accuracy = accuracy_score(y_test_eval, y_pred_eval)
            f1 = f1_score(y_test_eval, y_pred_eval, average='weighted', zero_division=0)
            logger.info(f"Evaluation Metrics - Accuracy: {accuracy:.4f}, F1 (weighted): {f1:.4f}")
            return {"accuracy": accuracy, "f1_weighted": f1}
        except Exception as e:
            logger.error(f"Error during model evaluation: {e}", exc_info=True)
            return {"accuracy": 0.0, "f1_weighted": 0.0}

    def load_model(self, artifact_path: str):
        """Loads the model object using the *injected* artifact service."""
        logger.info(f"Strategy {self.__class__.__name__}: Loading model from {artifact_path}")
        self.model = self.artifact_service.load_artifact(artifact_path)
        if self.model is None:
            raise IOError(f"Failed to load model from artifact path: {artifact_path}")
        logger.info(f"Model {self.model.__class__.__name__} loaded successfully.")

    def save_model(self, artifact_path: str) -> bool:
        """Saves the model object using the *injected* artifact service."""
        if self.model is None:
            logger.error("Cannot save model: Internal model object is None.")
            return False
        logger.info(f"Strategy {self.__class__.__name__}: Saving model to {artifact_path}")
        return self.artifact_service.save_artifact(self.model, artifact_path)