# worker/ml/services/strategies/lightgbm_strategy.py
import logging
import time
from typing import Any, Dict, List, Optional, Type  # Added Optional

import lightgbm as lgb  # Import LightGBM
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from services.interfaces.i_artifact_service import IArtifactService
from shared.schemas.enums import ModelTypeEnum
from shared.schemas.ml_model_type_definition import HyperparameterDefinitionSchema

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

    @staticmethod
    def get_supported_model_types_with_schemas() -> Dict[ModelTypeEnum, List[HyperparameterDefinitionSchema]]:
        lgbm_schema = [
            HyperparameterDefinitionSchema(name="boosting_type", type="text_choice", default_value="gbdt", options=[{"value":"gbdt", "label":"Gradient Boosting Decision Tree"}, {"value":"dart", "label":"DART"}, {"value":"goss", "label":"Gradient-based One-Side Sampling"}, {"value":"rf", "label":"Random Forest"}], description="Type of boosting algorithm."),
            HyperparameterDefinitionSchema(name="num_leaves", type="integer", default_value=31, description="Maximum tree leaves for base learners.", range={"min":2, "max":200}),
            HyperparameterDefinitionSchema(name="learning_rate", type="float", default_value=0.1, description="Boosting learning rate.", range={"min":0.001, "max":1.0}, log=True),
            HyperparameterDefinitionSchema(name="n_estimators", type="integer", default_value=100, description="Number of boosted trees to fit.", range={"min":10, "max":1000, "step":10}),
            HyperparameterDefinitionSchema(name="max_depth", type="integer", default_value=-1, description="Maximum tree depth for base learners, -1 means no limit.", range={"min":-1, "max":50}),
            HyperparameterDefinitionSchema(name="min_child_samples", type="integer", default_value=20, alias="min_data_in_leaf", description="Minimum number of data needed in a child (leaf).", range={"min":1, "max":100}),
            HyperparameterDefinitionSchema(name="subsample", type="float", default_value=1.0, alias="bagging_fraction", description="Subsample ratio of the training instance.", range={"min":0.1, "max":1.0}),
            HyperparameterDefinitionSchema(name="colsample_bytree", type="float", default_value=1.0, alias="feature_fraction", description="Subsample ratio of columns when constructing each tree.", range={"min":0.1, "max":1.0}),
            HyperparameterDefinitionSchema(name="reg_alpha", type="float", default_value=0.0, alias="lambda_l1", description="L1 regularization term on weights.", range={"min":0.0, "max":1.0}),
            HyperparameterDefinitionSchema(name="reg_lambda", type="float", default_value=0.0, alias="lambda_l2", description="L2 regularization term on weights.", range={"min":0.0, "max":1.0}),
            HyperparameterDefinitionSchema(name="is_unbalance", type="boolean", default_value=False, alias="scale_pos_weight_for_unbalanced", description="Set to true if training data is unbalanced. For binary classification, it sets scale_pos_weight to (#neg_samples/#pos_samples)."), # Note: LightGBM can also take scale_pos_weight directly as float
        ]
        return {
            ModelTypeEnum.LIGHTGBM_CLASSIFIER: lgbm_schema,
        }

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

        training_time_seconds = 0.0
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

            start_time = time.perf_counter()
            self.model.fit(X_train, y_train, **fit_params)
            end_time = time.perf_counter()
            training_time_seconds = round(end_time - start_time, 3)

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

        metrics["training_time_seconds"] = training_time_seconds

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
