# worker/ml/services/strategies/sklearn_strategy.py
import logging
from typing import Any, Dict, Type

import pandas as pd
from services.interfaces import IArtifactService
from sklearn.ensemble import (
    AdaBoostClassifier,
    GradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

from shared.schemas.enums import ModelTypeEnum

from .base_strategy import BaseModelStrategy, TrainResult

logger = logging.getLogger(__name__)


class SklearnStrategy(BaseModelStrategy):
    """Execution strategy for scikit-learn based models."""

    def __init__(
        self,
        model_type: ModelTypeEnum,
        model_config: Dict[str, Any],
        job_config: Dict[str, Any],
        artifact_service: IArtifactService,
    ):
        super().__init__(model_type, model_config, job_config, artifact_service)
        # self.model_type_enum is already set by base class

    def _initialize_model_internals(self):
        """No specific sklearn initialization needed post __init__ in this strategy."""
        pass

    def _get_model_class(self) -> Type:
        """Return the estimator class corresponding to the self.model_type_enum."""
        if self.model_type_enum == ModelTypeEnum.SKLEARN_RANDOMFOREST:
            return RandomForestClassifier
        elif self.model_type_enum == ModelTypeEnum.SKLEARN_LOGISTICREGRESSION:
            return LogisticRegression
        elif self.model_type_enum == ModelTypeEnum.SKLEARN_SVC:
            return SVC
        elif self.model_type_enum == ModelTypeEnum.SKLEARN_GRADIENTBOOSTINGCLASSIFIER:
            return GradientBoostingClassifier
        elif self.model_type_enum == ModelTypeEnum.SKLEARN_ADABOOSTCLASSIFIER:
            return AdaBoostClassifier
        elif self.model_type_enum == ModelTypeEnum.SKLEARN_DECISIONTREECLASSIFIER:
            return DecisionTreeClassifier
        elif self.model_type_enum == ModelTypeEnum.SKLEARN_KNNCLASSIFIER:
            return KNeighborsClassifier
        # Add other sklearn models here
        else:
            raise ValueError(
                f"Unsupported scikit-learn model type for SklearnStrategy: {self.model_type_enum.value}"
            )

    def _get_model_instance(self) -> Any:
        """
        Instantiates the scikit-learn model with filtered hyperparameters.
        This method creates a new instance, typically used before fitting.
        The `self.model` attribute will be set to the *fitted* model in the `train` method.
        """
        model_cls = self._get_model_class()

        # Get random_state from job_config, default if not present
        random_state = self.job_config.get("random_seed", 42)

        # Get valid parameters for the model class
        # Instantiate a default version to get params, or use inspect
        try:
            # For models that need random_state at init to get other params correctly.
            if "random_state" in model_cls().get_params():
                default_instance = model_cls(random_state=random_state)
            else:
                default_instance = model_cls()
            valid_params_keys = default_instance.get_params(deep=True).keys()
        except Exception as e:
            logger.warning(
                f"Could not get params for {model_cls.__name__}, using all model_config keys. Error: {e}"
            )
            valid_params_keys = self.model_config.keys()

        # Filter self.model_config against valid parameters
        filtered_config = {
            k: v for k, v in self.model_config.items() if k in valid_params_keys
        }

        # Ensure random_state is set if the model supports it and it's not already in filtered_config
        # Also check if 'probability' is a param for SVC and set if not provided and model_type is SVC
        if model_cls == SVC:
            if (
                "probability" in valid_params_keys
                and "probability" not in filtered_config
            ):
                logger.info("Setting 'probability=True' by default for SVC model type.")
                filtered_config["probability"] = True  # Needed for predict_proba

        if (
            "random_state" in valid_params_keys
            and "random_state" not in filtered_config
        ):
            filtered_config["random_state"] = random_state

        logger.debug(
            f"Instantiating {model_cls.__name__} with filtered config: {filtered_config}"
        )
        return model_cls(**filtered_config)

    def train(self, X: pd.DataFrame, y: pd.Series) -> TrainResult:
        """Trains a scikit-learn model with train/test split evaluation."""
        logger.info(
            f"SklearnStrategy: Starting training for model type: {self.model_type_enum.value}"
        )
        logger.info(f"Training data shape: X={X.shape}, y={y.shape}")

        test_size = self.job_config.get("eval_test_split_size", 0.2)
        random_state = self.job_config.get("random_seed", 42)
        X_train, X_test, y_train, y_test = (
            X,
            pd.DataFrame(),
            y,
            pd.Series(),
        )  # Initialize

        if 0.0 < test_size < 1.0:
            try:
                stratify_col = (
                    y
                    if pd.api.types.is_integer_dtype(y) or pd.api.types.is_bool_dtype(y)
                    else None
                )
                X_train, X_test, y_train, y_test = train_test_split(
                    X,
                    y,
                    test_size=test_size,
                    random_state=random_state,
                    stratify=stratify_col,
                )
                logger.info(f"Data split: Train={X_train.shape}, Test={X_test.shape}")
            except (
                ValueError
            ) as e:  # Handles issues with stratify if classes are too few
                logger.warning(
                    f"Stratified split failed ('{e}'). Falling back to non-stratified split."
                )
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=test_size, random_state=random_state
                )
        else:
            logger.info(
                "Full dataset used for training (no test split). Test evaluation will be skipped."
            )
            X_train, y_train = X, y
            # X_test, y_test remain empty

        try:
            current_model_instance = self._get_model_instance()  # Get a fresh instance
            logger.info(f"Fitting {current_model_instance.__class__.__name__}...")
            current_model_instance.fit(X_train, y_train)
            self.model = current_model_instance  # Assign fitted model to self.model
            logger.info("Model fitting complete.")
        except Exception as e:
            logger.error(f"Error during model fitting: {e}", exc_info=True)
            raise

        metrics = {}
        if not X_test.empty and not y_test.empty:
            logger.info("Evaluating sklearn model on the test set...")
            metrics = self.evaluate(X_test, y_test)  # Uses self.model
        else:
            logger.warning("No test set available for evaluation during training.")
            # Optionally evaluate on training data, but be cautious interpreting these
            # metrics_train = self.evaluate(X_train, y_train)
            # metrics = {f"train_{k}": v for k, v in metrics_train.items()}

        return TrainResult(model=self.model, metrics=metrics)

    def predict(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Generates predictions using the fitted scikit-learn model."""
        if self.model is None:
            raise RuntimeError("Sklearn model is not fitted or loaded. Cannot predict.")

        logger.info(
            f"SklearnStrategy: Generating predictions for {len(data)} samples using {self.model.__class__.__name__}..."
        )
        try:
            predictions_array = self.model.predict(data)
            result = {"predictions": predictions_array.tolist()}

            if hasattr(self.model, "predict_proba"):
                probabilities_array = self.model.predict_proba(data)
                result["probabilities"] = probabilities_array.tolist()
            else:
                # For models like SVC without probability=True, or other regressors
                logger.warning(
                    f"Model {self.model.__class__.__name__} does not support predict_proba or it's not enabled."
                )
                # Create dummy probabilities if needed by downstream XAI, or handle appropriately
                # For binary classification, can try to infer based on decision_function if available
                # result["probabilities"] = [[1.0 - p, p] for p in (predictions_array > 0).astype(float)] # Example placeholder

            return result
        except Exception as e:
            logger.error(f"Error during sklearn prediction: {e}", exc_info=True)
            raise
