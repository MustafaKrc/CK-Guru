# worker/ml/services/strategies/lightgbm_strategy.py
import logging
from typing import Any, Dict, Optional, Type  # Added Optional

import lightgbm as lgb  # Import LightGBM
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from services.interfaces.i_artifact_service import IArtifactService
from shared.schemas.enums import ModelTypeEnum

from .base_strategy import BaseModelStrategy, TrainResult

logger = logging.getLogger(__name__)


class LightGBMStrategy(BaseModelStrategy):
    """Execution strategy for LightGBM models."""

    def __init__(
        self,
        model_type: ModelTypeEnum,  # Should be LIGHTGBM_CLASSIFIER
        model_config: Dict[str, Any],
        job_config: Dict[str, Any],
        artifact_service: IArtifactService,
    ):
        super().__init__(model_type, model_config, job_config, artifact_service)
        self.label_encoder: Optional[LabelEncoder] = None

    def _initialize_model_internals(self):
        if "objective" not in self.model_config:
            self.model_config["objective"] = (
                "binary"  # Common for binary classification
            )
            logger.info("LightGBMStrategy: Defaulting 'objective' to 'binary'.")

    def _get_model_class(self) -> Type:
        return lgb.LGBMClassifier

    def _get_model_instance(self) -> Any:
        model_cls = self._get_model_class()
        current_config = self.model_config.copy()

        if "random_state" not in current_config and "random_seed" in self.job_config:
            current_config["random_state"] = self.job_config.get("random_seed", 42)
        elif "random_state" not in current_config:
            current_config["random_state"] = 42

        # LightGBM specific: n_jobs for training can be set.
        # if 'n_jobs' not in current_config:
        #     current_config['n_jobs'] = -1 # Use all available cores by default

        logger.debug(
            f"Instantiating LGBMClassifier with effective config: {current_config}"
        )
        return model_cls(**current_config)

    def train(self, X: pd.DataFrame, y: pd.Series) -> TrainResult:
        logger.info(
            f"LightGBMStrategy: Starting training for model type: {self.model_type_enum.value}"
        )
        logger.info(f"Training data shape: X={X.shape}, y={y.shape}")

        y_processed = y.copy()
        if not pd.api.types.is_numeric_dtype(y_processed):
            logger.info(
                "LightGBMStrategy: Target variable is not numeric. Applying LabelEncoder."
            )
            self.label_encoder = LabelEncoder()
            y_processed = pd.Series(
                self.label_encoder.fit_transform(y_processed),
                index=y.index,
                name=y.name,
            )

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
                f"LightGBM Data split: Train={X_train.shape}, Test={X_test.shape}"
            )
        else:
            logger.info(
                "LightGBM: Full dataset used for training. Test evaluation will be on training data or skipped."
            )
            X_train, y_train = X, y_processed

        try:
            self.model = self._get_model_instance()
            logger.info(f"Fitting {self.model.__class__.__name__}...")

            fit_params = {}
            # LightGBM uses callbacks for early stopping
            if "early_stopping_rounds" in self.model_config and not X_test.empty:
                callbacks = [
                    lgb.early_stopping(
                        stopping_rounds=self.model_config["early_stopping_rounds"],
                        verbose=self.model_config.get(
                            "verbose_eval", -1
                        ),  # -1 for no verbose, 1 for iter log
                    )
                ]
                fit_params["callbacks"] = callbacks
                fit_params["eval_set"] = [(X_test, y_test)]
                # eval_metric might be needed in fit_params or already in model_config
                if "metric" in self.model_config:
                    fit_params["eval_metric"] = self.model_config["metric"]
                logger.info(
                    f"Using LightGBM early stopping with {self.model_config['early_stopping_rounds']} rounds."
                )

            self.model.fit(X_train, y_train, **fit_params)
            logger.info("LightGBM model fitting complete.")
        except Exception as e:
            logger.error(f"Error during LightGBM model fitting: {e}", exc_info=True)
            raise

        metrics = {}
        if not X_test.empty and not y_test.empty:
            logger.info("Evaluating LightGBM model on the test set...")
            metrics = self.evaluate(X_test, y_test)
        elif not X.empty and not y_processed.empty:
            logger.warning(
                "No test set for evaluation. Evaluating LightGBM model on training data."
            )
            metrics_train = self.evaluate(X_train, y_train)
            metrics = {f"train_{k}": v for k, v in metrics_train.items()}

        return TrainResult(model=self.model, metrics=metrics)

    def predict(self, data: pd.DataFrame) -> Dict[str, Any]:
        if self.model is None:
            raise RuntimeError(
                "LightGBM model is not fitted or loaded. Cannot predict."
            )

        logger.info(
            f"LightGBMStrategy: Generating predictions for {len(data)} samples..."
        )
        try:
            predictions_raw = self.model.predict(data)

            if self.label_encoder:
                predictions_final = self.label_encoder.inverse_transform(
                    predictions_raw
                )
            else:
                predictions_final = predictions_raw

            result = {"predictions": predictions_final.tolist()}

            if hasattr(self.model, "predict_proba"):
                probabilities_array = self.model.predict_proba(data)
                result["probabilities"] = probabilities_array.tolist()
            else:
                logger.warning(
                    f"LightGBM model {self.model.__class__.__name__} does not support predict_proba."
                )

            return result
        except Exception as e:
            logger.error(f"Error during LightGBM prediction: {e}", exc_info=True)
            raise

    # LightGBM also has its own save/load (model.booster_.save_model(), lgb.Booster(model_file=...))
    # Relying on joblib via artifact_service for now for the scikit-learn wrapper.
