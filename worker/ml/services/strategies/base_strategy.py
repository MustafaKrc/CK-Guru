# worker/ml/services/strategies/base_strategy.py
import logging
from abc import ABC, abstractmethod
from inspect import Parameter, signature
from typing import Any, Dict, NamedTuple, Set, Type

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.utils.multiclass import type_of_target

from services.interfaces import IArtifactService
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
                "roc_auc": 0.0,
                "log_loss": str(float("inf")),
            }

        logger.info(
            f"Evaluating model {self.model.__class__.__name__} on test data ({len(X_test)} samples)..."
        )
        metrics: Dict[str, float] = {}
        try:
            y_pred = self.model.predict(X_test)
            y_test_eval = pd.Series(y_test).astype(int)
            y_pred_eval = pd.Series(y_pred).astype(int)

            metrics["accuracy"] = round(accuracy_score(y_test_eval, y_pred_eval), 4)
            metrics["f1_weighted"] = round(
                f1_score(y_test_eval, y_pred_eval, average="weighted", zero_division=0),
                4,
            )
            metrics["precision_weighted"] = round(
                precision_score(
                    y_test_eval, y_pred_eval, average="weighted", zero_division=0
                ),
                4,
            )
            metrics["recall_weighted"] = round(
                recall_score(
                    y_test_eval, y_pred_eval, average="weighted", zero_division=0
                ),
                4,
            )

            if hasattr(self.model, "predict_proba"):
                try:
                    y_pred_proba = self.model.predict_proba(X_test)
                    target_type = type_of_target(y_test_eval)

                    if target_type == "binary":
                        metrics["roc_auc"] = round(
                            roc_auc_score(y_test_eval, y_pred_proba[:, 1]), 4
                        )
                    elif target_type == "multiclass":
                        if hasattr(self.model, "classes_"):
                            metrics["roc_auc"] = round(
                                roc_auc_score(
                                    y_test_eval,
                                    y_pred_proba,
                                    multi_class="ovr",
                                    average="weighted",
                                    labels=self.model.classes_,
                                ),
                                4,
                            )
                        else:
                            metrics["roc_auc"] = round(
                                roc_auc_score(
                                    y_test_eval,
                                    y_pred_proba,
                                    multi_class="ovr",
                                    average="weighted",
                                ),
                                4,
                            )
                    else:
                        logger.warning(
                            f"ROC AUC not calculated for target type: {target_type}"
                        )
                        metrics["roc_auc"] = 0.0

                    # Ensure labels match for log_loss if model has classes_ attribute
                    log_loss_labels = getattr(self.model, "classes_", None)
                    if log_loss_labels is not None and not np.array_equal(
                        np.sort(y_test_eval.unique()), np.sort(log_loss_labels)
                    ):
                        logger.warning(
                            "Mismatch between y_test unique labels and model.classes_ for log_loss. This might lead to errors or incorrect log_loss values."
                        )
                        # You might choose to not calculate log_loss or handle this case differently
                        metrics["log_loss"] = str(float("inf"))
                    else:
                        metrics["log_loss"] = round(
                            log_loss(y_test_eval, y_pred_proba, labels=log_loss_labels),
                            4,
                        )

                except ValueError as ve:  # Catch specific ValueError from metrics
                    logger.warning(
                        f"Could not calculate probability-based metrics (ROC AUC, Log Loss) due to ValueError: {ve}. This can happen with single class in y_true or mismatched labels."
                    )
                    metrics["roc_auc"] = 0.0
                    metrics["log_loss"] = str(float("inf"))
                except Exception as proba_metrics_err:
                    logger.warning(
                        f"Could not calculate probability-based metrics (ROC AUC, Log Loss): {proba_metrics_err}"
                    )
                    metrics["roc_auc"] = 0.0
                    metrics["log_loss"] = str(float("inf"))
            else:
                logger.warning(
                    f"Model {self.model.__class__.__name__} does not have predict_proba. ROC AUC and Log Loss cannot be calculated."
                )
                metrics["roc_auc"] = 0.0
                metrics["log_loss"] = str(float("inf"))

            logger.info(f"Evaluation Metrics: {metrics}")
            return metrics
        except Exception as e:
            logger.error(f"Error during model evaluation: {e}", exc_info=True)
            return {
                "accuracy": 0.0,
                "f1_weighted": 0.0,
                "precision_weighted": 0.0,
                "recall_weighted": 0.0,
                "roc_auc": 0.0,
                "log_loss": str(float("inf")),
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
