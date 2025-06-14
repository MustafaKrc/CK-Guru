# worker/ml/services/strategies/sklearn_strategy.py
import logging
import time
from typing import Any, Dict, List, Type

import pandas as pd
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

from services.interfaces import IArtifactService
from shared.schemas.enums import ModelTypeEnum
from shared.schemas.ml_model_type_definition import HyperparameterDefinitionSchema

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

    @staticmethod
    def get_supported_model_types_with_schemas() -> (
        Dict[ModelTypeEnum, List[HyperparameterDefinitionSchema]]
    ):
        """
        Returns a dictionary mapping supported ModelTypeEnum to their base hyperparameter schema.
        """
        # RandomForestClassifier Schema (already provided)
        rf_schema = [
            HyperparameterDefinitionSchema(
                name="n_estimators",
                type="integer",
                default_value=100,
                description="Number of trees in the forest.",
                range={"min": 10, "max": 1000, "step": 10},
            ),
            HyperparameterDefinitionSchema(
                name="criterion",
                type="text_choice",
                default_value="gini",
                description="Function to measure the quality of a split.",
                options=[
                    {"value": "gini", "label": "Gini Impurity"},
                    {"value": "entropy", "label": "Entropy"},
                    {"value": "log_loss", "label": "Log Loss"},
                ],
            ),
            HyperparameterDefinitionSchema(
                name="max_depth",
                type="integer",
                default_value=None,
                description="Maximum depth of the tree. If None, nodes are expanded until all leaves are pure.",
                range={"min": 1, "max": 100},
                required=False,
            ),
            HyperparameterDefinitionSchema(
                name="min_samples_split",
                type="integer",
                default_value=2,
                description="Minimum number of samples required to split an internal node.",
                range={"min": 2, "max": 50},
            ),
            HyperparameterDefinitionSchema(
                name="min_samples_leaf",
                type="integer",
                default_value=1,
                description="Minimum number of samples required to be at a leaf node.",
                range={"min": 1, "max": 50},
            ),
            HyperparameterDefinitionSchema(
                name="class_weight",
                type="text_choice",
                default_value=None,
                description="Weights associated with classes.",
                options=[
                    {"value": "balanced", "label": "Balanced"},
                    {"value": "balanced_subsample", "label": "Balanced Subsample"},
                    {"value": "None", "label": "None"},
                ],
                required=False,
            ),
            HyperparameterDefinitionSchema(
                name="max_features",
                type="text_choice",
                default_value="sqrt",
                description="Number of features to consider for best split.",
                options=[
                    {"value": "sqrt", "label": "SQRT"},
                    {"value": "log2", "label": "LOG2"},
                    {"value": "None", "label": "None (all features)"},
                    {"type": "integer", "label": "Integer Value"},
                    {"type": "float", "label": "Float Value (fraction)"},
                ],
            ),  # max_features can be int, float, or string
        ]

        # LogisticRegression Schema (already provided)
        lr_schema = [
            HyperparameterDefinitionSchema(
                name="penalty",
                type="text_choice",
                default_value="l2",
                options=[
                    {"value": "l1", "label": "L1 (Lasso)"},
                    {"value": "l2", "label": "L2 (Ridge)"},
                    {"value": "elasticnet", "label": "Elastic Net"},
                    {"value": "None", "label": "None (no penalty)"},
                ],
                description="Specify the norm of the penalty.",
            ),
            HyperparameterDefinitionSchema(
                name="C",
                type="float",
                default_value=1.0,
                description="Inverse of regularization strength; must be a positive float. Smaller values specify stronger regularization.",
                range={"min": 0.001, "max": 1000.0},
                log=True,
            ),  # Added log for Optuna
            HyperparameterDefinitionSchema(
                name="solver",
                type="text_choice",
                default_value="lbfgs",
                options=[
                    {"value": "lbfgs", "label": "L-BFGS"},
                    {
                        "value": "liblinear",
                        "label": "Liblinear (good for small datasets)",
                    },
                    {"value": "newton-cg", "label": "Newton-CG"},
                    {"value": "newton-cholesky", "label": "Newton Cholesky"},
                    {"value": "sag", "label": "SAG (good for large datasets)"},
                    {
                        "value": "saga",
                        "label": "SAGA (good for large datasets, supports L1)",
                    },
                ],
                description="Algorithm to use in the optimization problem.",
            ),
            HyperparameterDefinitionSchema(
                name="class_weight",
                type="text_choice",
                default_value=None,
                description="Weights associated with classes.",
                options=[
                    {"value": "balanced", "label": "Balanced"},
                    {"value": "None", "label": "None"},
                ],
                required=False,
            ),
            HyperparameterDefinitionSchema(
                name="max_iter",
                type="integer",
                default_value=100,
                description="Maximum number of iterations taken for the solvers to converge.",
                range={"min": 50, "max": 1000},
            ),
        ]

        # SVC Schema
        svc_schema = [
            HyperparameterDefinitionSchema(
                name="C",
                type="float",
                default_value=1.0,
                description="Regularization parameter. The strength of the regularization is inversely proportional to C.",
                range={"min": 0.01, "max": 100.0},
                log=True,
            ),
            HyperparameterDefinitionSchema(
                name="kernel",
                type="text_choice",
                default_value="rbf",
                options=[
                    {"value": "linear", "label": "Linear"},
                    {"value": "poly", "label": "Polynomial"},
                    {"value": "rbf", "label": "RBF (Radial Basis Function)"},
                    {"value": "sigmoid", "label": "Sigmoid"},
                ],
                description="Specifies the kernel type to be used in the algorithm.",
            ),
            HyperparameterDefinitionSchema(
                name="degree",
                type="integer",
                default_value=3,
                description="Degree of the polynomial kernel function (‘poly’). Ignored by all other kernels.",
                range={"min": 1, "max": 10},
            ),
            HyperparameterDefinitionSchema(
                name="gamma",
                type="text_choice",
                default_value="scale",
                options=[
                    {"value": "scale", "label": "Scale (1 / (n_features * X.var()))"},
                    {"value": "auto", "label": "Auto (1 / n_features)"},
                    {"type": "float", "label": "Float value"},
                ],
                description="Kernel coefficient for ‘rbf’, ‘poly’ and ‘sigmoid’.",
            ),  # Gamma can also be float
            HyperparameterDefinitionSchema(
                name="class_weight",
                type="text_choice",
                default_value=None,
                description="Weights associated with classes.",
                options=[
                    {"value": "balanced", "label": "Balanced"},
                    {"value": "None", "label": "None"},
                ],
                required=False,
            ),
            HyperparameterDefinitionSchema(
                name="probability",
                type="boolean",
                default_value=False,
                description="Whether to enable probability estimates. Must be enabled prior to calling `predict_proba`.",
            ),
        ]

        # GradientBoostingClassifier Schema
        gb_schema = [
            HyperparameterDefinitionSchema(
                name="loss",
                type="text_choice",
                default_value="log_loss",
                options=[
                    {"value": "log_loss", "label": "Log-loss (deviance)"},
                    {"value": "exponential", "label": "Exponential (AdaBoost)"},
                ],
                description="Loss function to be optimized. 'log_loss' gives logistic regression for binary classification.",
            ),
            HyperparameterDefinitionSchema(
                name="learning_rate",
                type="float",
                default_value=0.1,
                description="Learning rate shrinks the contribution of each tree.",
                range={"min": 0.001, "max": 1.0},
                log=True,
            ),
            HyperparameterDefinitionSchema(
                name="n_estimators",
                type="integer",
                default_value=100,
                description="The number of boosting stages to perform.",
                range={"min": 10, "max": 1000, "step": 10},
            ),
            HyperparameterDefinitionSchema(
                name="subsample",
                type="float",
                default_value=1.0,
                description="The fraction of samples to be used for fitting the individual base learners.",
                range={"min": 0.1, "max": 1.0},
            ),
            HyperparameterDefinitionSchema(
                name="criterion",
                type="text_choice",
                default_value="friedman_mse",
                options=[
                    {"value": "friedman_mse", "label": "Friedman MSE"},
                    {"value": "squared_error", "label": "Squared Error"},
                ],
                description="The function to measure the quality of a split.",
            ),
            HyperparameterDefinitionSchema(
                name="max_depth",
                type="integer",
                default_value=3,
                description="Maximum depth of the individual regression estimators.",
                range={"min": 1, "max": 20},
            ),
            HyperparameterDefinitionSchema(
                name="min_samples_split",
                type="integer",
                default_value=2,
                description="Minimum number of samples required to split an internal node.",
                range={"min": 2, "max": 50},
            ),
            HyperparameterDefinitionSchema(
                name="min_samples_leaf",
                type="integer",
                default_value=1,
                description="Minimum number of samples required to be at a leaf node.",
                range={"min": 1, "max": 50},
            ),
            HyperparameterDefinitionSchema(
                name="max_features",
                type="text_choice",
                default_value=None,
                description="Number of features to consider for best split.",
                options=[
                    {"value": "sqrt", "label": "SQRT"},
                    {"value": "log2", "label": "LOG2"},
                    {"value": "None", "label": "None (all features)"},
                    {"type": "integer", "label": "Integer Value"},
                    {"type": "float", "label": "Float Value (fraction)"},
                ],
                required=False,
            ),
        ]

        # AdaBoostClassifier Schema
        ada_schema = [
            HyperparameterDefinitionSchema(
                name="estimator",
                type="string",
                default_value=None,
                description="The base estimator from which the boosted ensemble is built (e.g. DecisionTreeClassifier). If None, then the base estimator is DecisionTreeClassifier initialized with max_depth=1.",
                required=False,
            ),  # This is complex; for UI, might simplify or hardcode default.
            HyperparameterDefinitionSchema(
                name="n_estimators",
                type="integer",
                default_value=50,
                description="The maximum number of estimators at which boosting is terminated.",
                range={"min": 10, "max": 500, "step": 10},
            ),
            HyperparameterDefinitionSchema(
                name="learning_rate",
                type="float",
                default_value=1.0,
                description="Weight applied to each classifier at each boosting iteration.",
                range={"min": 0.001, "max": 2.0},
                log=True,
            ),
            HyperparameterDefinitionSchema(
                name="algorithm",
                type="text_choice",
                default_value="SAMME.R",
                options=[
                    {"value": "SAMME", "label": "SAMME"},
                    {"value": "SAMME.R", "label": "SAMME.R"},
                ],
                description="If ‘SAMME.R’ then use the SAMME.R real boosting algorithm. 'estimator' must support calculation of class probabilities. If ‘SAMME’ then use the SAMME discrete boosting algorithm.",
            ),
        ]

        # DecisionTreeClassifier Schema
        dt_schema = [
            HyperparameterDefinitionSchema(
                name="criterion",
                type="text_choice",
                default_value="gini",
                description="Function to measure the quality of a split.",
                options=[
                    {"value": "gini", "label": "Gini Impurity"},
                    {"value": "entropy", "label": "Entropy"},
                    {"value": "log_loss", "label": "Log Loss"},
                ],
            ),
            HyperparameterDefinitionSchema(
                name="splitter",
                type="text_choice",
                default_value="best",
                options=[
                    {"value": "best", "label": "Best"},
                    {"value": "random", "label": "Random"},
                ],
                description="Strategy used to choose the split at each node.",
            ),
            HyperparameterDefinitionSchema(
                name="max_depth",
                type="integer",
                default_value=None,
                description="Maximum depth of the tree.",
                range={"min": 1, "max": 100},
                required=False,
            ),
            HyperparameterDefinitionSchema(
                name="min_samples_split",
                type="integer",
                default_value=2,
                description="Minimum number of samples required to split an internal node.",
                range={"min": 2, "max": 50},
            ),
            HyperparameterDefinitionSchema(
                name="min_samples_leaf",
                type="integer",
                default_value=1,
                description="Minimum number of samples required to be at a leaf node.",
                range={"min": 1, "max": 50},
            ),
            HyperparameterDefinitionSchema(
                name="max_features",
                type="text_choice",
                default_value=None,
                description="Number of features to consider for best split.",
                options=[
                    {"value": "sqrt", "label": "SQRT"},
                    {"value": "log2", "label": "LOG2"},
                    {"value": "None", "label": "None (all features)"},
                    {"type": "integer", "label": "Integer Value"},
                    {"type": "float", "label": "Float Value (fraction)"},
                ],
                required=False,
            ),
            HyperparameterDefinitionSchema(
                name="class_weight",
                type="text_choice",
                default_value=None,
                description="Weights associated with classes.",
                options=[
                    {"value": "balanced", "label": "Balanced"},
                    {"value": "None", "label": "None"},
                ],
                required=False,
            ),
        ]

        # KNeighborsClassifier Schema
        knn_schema = [
            HyperparameterDefinitionSchema(
                name="n_neighbors",
                type="integer",
                default_value=5,
                description="Number of neighbors to use.",
                range={"min": 1, "max": 50},
            ),
            HyperparameterDefinitionSchema(
                name="weights",
                type="text_choice",
                default_value="uniform",
                options=[
                    {"value": "uniform", "label": "Uniform (all points equal weight)"},
                    {
                        "value": "distance",
                        "label": "Distance (closer neighbors have more influence)",
                    },
                ],
                description="Weight function used in prediction.",
            ),
            HyperparameterDefinitionSchema(
                name="algorithm",
                type="text_choice",
                default_value="auto",
                options=[
                    {"value": "auto", "label": "Auto"},
                    {"value": "ball_tree", "label": "Ball Tree"},
                    {"value": "kd_tree", "label": "KD Tree"},
                    {"value": "brute", "label": "Brute-force"},
                ],
                description="Algorithm used to compute the nearest neighbors.",
            ),
            HyperparameterDefinitionSchema(
                name="leaf_size",
                type="integer",
                default_value=30,
                description="Leaf size passed to BallTree or KDTree.",
                range={"min": 1, "max": 100},
            ),
            HyperparameterDefinitionSchema(
                name="p",
                type="integer",
                default_value=2,
                description="Power parameter for the Minkowski metric (1 for manhattan, 2 for euclidean).",
                range={"min": 1, "max": 5},
            ),
            HyperparameterDefinitionSchema(
                name="metric",
                type="string",
                default_value="minkowski",
                description="Metric to use for distance computation.",
            ),  # Can also be callable, simplify to string for UI.
        ]

        return {
            ModelTypeEnum.SKLEARN_RANDOMFOREST: rf_schema,
            ModelTypeEnum.SKLEARN_LOGISTICREGRESSION: lr_schema,
            ModelTypeEnum.SKLEARN_SVC: svc_schema,
            ModelTypeEnum.SKLEARN_GRADIENTBOOSTINGCLASSIFIER: gb_schema,
            ModelTypeEnum.SKLEARN_ADABOOSTCLASSIFIER: ada_schema,
            ModelTypeEnum.SKLEARN_DECISIONTREECLASSIFIER: dt_schema,
            ModelTypeEnum.SKLEARN_KNNCLASSIFIER: knn_schema,
        }

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

        training_time_seconds = 0.0
        try:
            current_model_instance = self._get_model_instance()  # Get a fresh instance
            logger.info(f"Fitting {current_model_instance.__class__.__name__}...")

            start_time = time.perf_counter()
            current_model_instance.fit(X_train, y_train)
            end_time = time.perf_counter()
            training_time_seconds = round(end_time - start_time, 3)

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

        metrics["training_time_seconds"] = training_time_seconds

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
