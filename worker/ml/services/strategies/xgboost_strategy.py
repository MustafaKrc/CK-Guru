# worker/ml/services/strategies/xgboost_strategy.py
import logging
from typing import Any, Dict, Optional, Type

import pandas as pd
import xgboost as xgb  # Import XGBoost
from services.interfaces.i_artifact_service import IArtifactService
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder  # For handling string labels if any

from shared.schemas.enums import ModelTypeEnum  # Though model_type is passed

from .base_strategy import BaseModelStrategy, TrainResult

logger = logging.getLogger(__name__)


class XGBoostStrategy(BaseModelStrategy):
    """Execution strategy for XGBoost models."""

    def __init__(
        self,
        model_type: ModelTypeEnum,  # Should be XGBOOST_CLASSIFIER
        model_config: Dict[str, Any],
        job_config: Dict[str, Any],
        artifact_service: IArtifactService,
    ):
        super().__init__(model_type, model_config, job_config, artifact_service)
        self.label_encoder: Optional[LabelEncoder] = (
            None  # For target variable encoding
        )

    def _initialize_model_internals(self):
        # XGBoost specific initializations, if any, could go here.
        # For now, ensuring 'objective' is set based on problem type.
        if "objective" not in self.model_config:
            # Assuming binary classification for defect prediction
            self.model_config["objective"] = "binary:logistic"
            logger.info(
                "XGBoostStrategy: Defaulting 'objective' to 'binary:logistic'."
            )

    def _get_model_class(self) -> Type:
        """Return the XGBoost classifier class."""
        return xgb.XGBClassifier

    def _get_model_instance(self) -> Any:
        """Instantiates the XGBoost model."""
        model_cls = self._get_model_class()

        # XGBoost uses 'seed' for reproducibility, not 'random_state' directly in constructor
        # for the main part, but some underlying components might use random_state.
        # It's better to pass random_state to fit method's eval_set if used,
        # or set it if model_config explicitly allows it.
        # Most XGBoost params are passed directly.

        current_config = self.model_config.copy()  # Start with HPs

        # Add/override random_state if job_config has it and model supports it.
        # XGBClassifier itself takes random_state.
        if "random_state" not in current_config and "random_seed" in self.job_config:
            current_config["random_state"] = self.job_config.get("random_seed", 42)
        elif "random_state" in current_config:  # If user provided random_state in HPs
            pass  # Use user-provided random_state
        else:  # Default if neither provided
            current_config["random_state"] = 42

        # Ensure use_label_encoder is False if y is already numeric, to avoid warnings/errors
        # This is tricky because we don't have y here. Assume it's handled in train().
        # XGBoost >=1.3.0 defaults use_label_encoder=True, but it's deprecated and will be removed.
        # XGBoost >=1.6.0 defaults use_label_encoder=None which behaves like False.
        # Best to explicitly set it if needed or rely on newer XGBoost versions.
        if "use_label_encoder" not in current_config:
            current_config["use_label_encoder"] = False  # Recommended for newer XGBoost
            logger.debug(
                "XGBoostStrategy: Setting 'use_label_encoder=False'. Ensure target is numerically encoded if needed."
            )

        logger.debug(
            f"Instantiating XGBClassifier with effective config: {current_config}"
        )
        return model_cls(**current_config)

    def train(self, X: pd.DataFrame, y: pd.Series) -> TrainResult:
        logger.info(
            f"XGBoostStrategy: Starting training for model type: {self.model_type_enum.value}"
        )
        logger.info(f"Training data shape: X={X.shape}, y={y.shape}")

        # Handle target encoding if y is not numeric (e.g. string labels)
        y_processed = y.copy()
        if not pd.api.types.is_numeric_dtype(y_processed):
            logger.info(
                "XGBoostStrategy: Target variable is not numeric. Applying LabelEncoder."
            )
            self.label_encoder = LabelEncoder()
            y_processed = pd.Series(
                self.label_encoder.fit_transform(y_processed),
                index=y.index,
                name=y.name,
            )
            logger.info(f"Target classes after encoding: {self.label_encoder.classes_}")

        test_size = self.job_config.get("eval_test_split_size", 0.2)
        random_state_for_split = self.job_config.get("random_seed", 42)
        X_train, X_test, y_train, y_test = X, pd.DataFrame(), y_processed, pd.Series()

        if 0.0 < test_size < 1.0:
            stratify_col = y_train if y_train.nunique() > 1 else None
            X_train, X_test, y_train, y_test = train_test_split(
                X,
                y_processed,
                test_size=test_size,
                random_state=random_state_for_split,
                stratify=stratify_col,
            )
            logger.info(
                f"XGBoost Data split: Train={X_train.shape}, Test={X_test.shape}"
            )
        else:
            logger.info(
                "XGBoost: Full dataset used for training. Test evaluation will be on training data or skipped."
            )
            X_train, y_train = X, y_processed
            # X_test, y_test remain empty if no split

        try:
            self.model = self._get_model_instance()  # Get a fresh configured instance
            logger.info(f"Fitting {self.model.__class__.__name__}...")

            # For early stopping with XGBoost:
            eval_set = []
            if not X_test.empty and not y_test.empty:
                eval_set = [(X_test, y_test)]

            fit_params = {}
            if "early_stopping_rounds" in self.model_config and eval_set:
                fit_params["early_stopping_rounds"] = self.model_config[
                    "early_stopping_rounds"
                ]
                fit_params["eval_set"] = eval_set
                # Verbose can be a model_config param too
                fit_params["verbose"] = self.model_config.get("verbose_eval", False)
                logger.info(
                    f"Using early stopping with {fit_params['early_stopping_rounds']} rounds."
                )

            self.model.fit(X_train, y_train, **fit_params)
            logger.info("XGBoost model fitting complete.")
        except Exception as e:
            logger.error(f"Error during XGBoost model fitting: {e}", exc_info=True)
            raise

        metrics = {}
        if not X_test.empty and not y_test.empty:
            logger.info("Evaluating XGBoost model on the test set...")
            # The evaluate method from base_strategy uses self.model.predict, which is fine
            metrics = self.evaluate(X_test, y_test)
        elif (
            not X.empty and not y_processed.empty
        ):  # If no test set, evaluate on training data (use with caution)
            logger.warning(
                "No test set for evaluation. Evaluating XGBoost model on training data."
            )
            metrics_train = self.evaluate(X_train, y_train)
            metrics = {f"train_{k}": v for k, v in metrics_train.items()}

        return TrainResult(model=self.model, metrics=metrics)

    def predict(self, data: pd.DataFrame) -> Dict[str, Any]:
        if self.model is None:
            raise RuntimeError("XGBoost model is not fitted or loaded. Cannot predict.")

        logger.info(
            f"XGBoostStrategy: Generating predictions for {len(data)} samples..."
        )
        try:
            predictions_raw = self.model.predict(
                data
            )  # Raw predictions (could be labels or encoded labels)

            # If label encoder was used during training, inverse transform predictions
            if self.label_encoder:
                predictions_final = self.label_encoder.inverse_transform(
                    predictions_raw
                )
            else:
                predictions_final = (
                    predictions_raw  # Assume they are already in the desired format
                )

            result = {"predictions": predictions_final.tolist()}

            if hasattr(self.model, "predict_proba"):
                probabilities_array = self.model.predict_proba(data)
                result["probabilities"] = probabilities_array.tolist()
            else:
                logger.warning(
                    f"XGBoost model {self.model.__class__.__name__} does not support predict_proba."
                )

            return result
        except Exception as e:
            logger.error(f"Error during XGBoost prediction: {e}", exc_info=True)
            raise

    # XGBoost has its own save/load. Using joblib via artifact_service is also an option
    # and might be simpler if it handles XGBoost objects well.
    # For "true" XGBoost format, you'd save to a local temp file then upload via artifact_service.fs.put()
    # For now, we rely on the base_strategy's save/load which uses artifact_service.save_artifact (joblib)
    # This is generally fine for XGBoost scikit-learn wrapper objects.
