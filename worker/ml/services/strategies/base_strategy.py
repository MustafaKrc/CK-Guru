# worker/ml/services/strategies/base_strategy.py
import logging
from abc import ABC, abstractmethod
from inspect import Parameter, signature
from typing import Any, Dict, NamedTuple, Set, Type

import pandas as pd
from services.interfaces import IArtifactService
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from shared.schemas.enums import ModelTypeEnum

logger = logging.getLogger(__name__)


# Define a structure for training results
class TrainResult(NamedTuple):
    model: Any
    metrics: Dict[str, float]


class BaseModelStrategy(ABC):
    """Abstract base class for model-specific execution strategies."""

    def __init__(
        self,
        model_type: ModelTypeEnum,
        model_config: Dict[str, Any],  # Hyperparameters for this instance
        job_config: Dict[str, Any],  # Overall job config (e.g., random_seed)
        artifact_service: IArtifactService,
    ):
        """
        Initializes the strategy with configs and artifact service.
        """
        self.model_type_enum: ModelTypeEnum = model_type
        self.model_config: Dict[str, Any] = model_config
        self.job_config: Dict[str, Any] = job_config
        self.artifact_service: IArtifactService = artifact_service
        self.model: Any = None  # Holds the actual trained model object
        self._initialize_model_internals()
        logger.debug(
            f"Initialized strategy: {self.__class__.__name__} for model type {self.model_type_enum.value}"
        )

    def _initialize_model_internals(self):
        """Optional hook for subclasses to initialize specific things after base __init__."""
        pass

    @abstractmethod
    def _get_model_class(self) -> Type:
        """
        Return the *class* (not instance) of the underlying ML model.
        Example: `return RandomForestClassifier`
        """
        pass

    @abstractmethod
    def _get_model_instance(self) -> Any:
        """
        Subclasses implement to instantiate their specific ML model using
        `self.model_config` and `self.job_config` (e.g., for random_seed).
        This method should set `self.model` if it's creating the primary model instance
        to be used by train/predict. However, typically `train` sets `self.model`.
        This method is more about getting a fresh instance for operations like CV in Optuna.
        For direct training, `train` will call this and then fit.
        """
        pass

    @abstractmethod
    def train(self, X: pd.DataFrame, y: pd.Series) -> TrainResult:
        """
        Trains the model using the provided data.
        This method should:
        1. Get a model instance via `_get_model_instance()`.
        2. Fit the model.
        3. Set `self.model` to the fitted model.
        4. Evaluate the model.
        5. Return a TrainResult.
        """
        pass

    @abstractmethod
    def predict(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Generates predictions using the trained `self.model`.
        Should return a dictionary, e.g.,
        `{"predictions": [...], "probabilities": [[...],[...]]}`
        """
        pass

    def evaluate(self, X_test: pd.DataFrame, y_test: pd.Series) -> Dict[str, float]:
        """
        Default evaluation logic using common classification metrics.
        Assumes `self.model` is a trained model compatible with scikit-learn's API.
        Subclasses can override if different evaluation is needed.
        """
        if self.model is None:
            logger.error("Model is not available for evaluation (None).")
            raise RuntimeError("Model not trained or loaded for evaluation.")
        if not hasattr(self.model, "predict"):
            logger.error(
                f"Model type {type(self.model).__name__} does not have a 'predict' method."
            )
            return {
                "accuracy": 0.0,
                "f1_weighted": 0.0,
                "precision_weighted": 0.0,
                "recall_weighted": 0.0,
            }

        logger.info(
            f"Evaluating model {self.model.__class__.__name__} on test data ({len(X_test)} samples)..."
        )
        try:
            y_pred = self.model.predict(X_test)

            # Ensure y_test and y_pred are 1D arrays of the same type for metrics
            y_test_eval = pd.Series(y_test).astype(int)
            y_pred_eval = pd.Series(y_pred).astype(int)

            accuracy = accuracy_score(y_test_eval, y_pred_eval)
            f1 = f1_score(y_test_eval, y_pred_eval, average="weighted", zero_division=0)
            precision = precision_score(
                y_test_eval, y_pred_eval, average="weighted", zero_division=0
            )
            recall = recall_score(
                y_test_eval, y_pred_eval, average="weighted", zero_division=0
            )

            metrics = {
                "accuracy": round(accuracy, 4),
                "f1_weighted": round(f1, 4),
                "precision_weighted": round(precision, 4),
                "recall_weighted": round(recall, 4),
            }
            logger.info(f"Evaluation Metrics: {metrics}")
            return metrics
        except Exception as e:
            logger.error(f"Error during model evaluation: {e}", exc_info=True)
            return {
                "accuracy": 0.0,
                "f1_weighted": 0.0,
                "precision_weighted": 0.0,
                "recall_weighted": 0.0,
            }

    def get_hyperparameter_space(self) -> Set[str]:
        """
        Returns the names of constructor arguments that look like
        real hyperparameters (i.e., exclude *args/**kwargs, 'self', etc.).
        Works for scikit-learn and many other Python ML libraries.
        Subclasses can override if introspection isn't suitable.
        """
        try:
            model_cls = self._get_model_class()
            if (
                model_cls is None
            ):  # Should not happen if _get_model_class is implemented correctly
                logger.warning(
                    f"Strategy {self.__class__.__name__}: _get_model_class() returned None."
                )
                return set()

            sig = signature(model_cls.__init__)
            hp_names = {
                name
                for name, param in sig.parameters.items()
                if name != "self"
                and param.kind
                in (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY)
            }
            return hp_names
        except Exception as e:
            logger.error(
                f"Error introspecting hyperparameter space for {self.__class__.__name__}: {e}",
                exc_info=True,
            )
            return set()

    def load_model(self, artifact_path: str):
        """Loads the model object using the injected artifact service."""
        logger.info(
            f"Strategy {self.__class__.__name__}: Loading model from {artifact_path}"
        )
        self.model = self.artifact_service.load_artifact(artifact_path)
        if self.model is None:
            raise IOError(f"Failed to load model from artifact path: {artifact_path}")
        logger.info(
            f"Model {self.model.__class__.__name__} loaded successfully via {self.__class__.__name__}."
        )

    def save_model(self, artifact_path: str) -> bool:
        """Saves the model object using the injected artifact service."""
        if self.model is None:
            logger.error(
                f"Strategy {self.__class__.__name__}: Cannot save model, internal model object is None."
            )
            return False
        logger.info(
            f"Strategy {self.__class__.__name__}: Saving model to {artifact_path}"
        )
        return self.artifact_service.save_artifact(self.model, artifact_path)
