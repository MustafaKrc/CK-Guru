# worker/ml/services/hp_search_objective.py
import logging
from typing import Any, Dict, List  # Added List

import numpy as np
import optuna
import pandas as pd
from optuna.trial import Trial  # Explicit import of Trial
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    make_scorer,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score

from services.interfaces import IArtifactService
from shared.schemas.enums import ModelTypeEnum, ObjectiveMetricEnum
from shared.schemas.hp_search_job import HPSuggestion

from .factories.model_strategy_factory import create_model_strategy

logger = logging.getLogger(__name__)


class Objective:
    """Wraps the objective function for Optuna study."""

    def __init__(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        model_type_enum: ModelTypeEnum,
        hp_space_config: List[HPSuggestion],
        base_job_config: Dict[str, Any],
        artifact_service: IArtifactService,
    ):
        self.X = X
        self.y = y
        self.model_type_enum = model_type_enum  # Store model type
        self.hp_space_config = hp_space_config
        self.base_job_config = base_job_config  # This is HPSearchConfig from DB
        self.artifact_service = artifact_service  # Store artifact service

        # Extract Optuna-specific config from the base_job_config
        self.optuna_config = base_job_config.get("optuna_config", {})
        if not isinstance(self.optuna_config, dict):  # Ensure it's a dict
            logger.warning(
                "optuna_config in base_job_config is not a dict. Using empty dict."
            )
            self.optuna_config = {}

        self.objective_metric_str = self.optuna_config.get(
            "objective_metric", ObjectiveMetricEnum.F1_WEIGHTED.value
        )
        try:
            self.objective_metric_enum = ObjectiveMetricEnum(self.objective_metric_str)
        except ValueError:
            logger.warning(
                f"Invalid objective_metric '{self.objective_metric_str}'. Defaulting to F1_WEIGHTED."
            )
            self.objective_metric_enum = ObjectiveMetricEnum.F1_WEIGHTED
            self.objective_metric_str = self.objective_metric_enum.value

        self.cv_folds = self.optuna_config.get("hp_search_cv_folds", 3)
        # Random seed for CV split, not necessarily for model instantiation within trial
        self.cv_random_seed = base_job_config.get("random_seed", 42)
        self.scorer = self._create_scorer()

        logger.debug(
            f"HP Search Objective initialized. Metric: {self.objective_metric_str}, "
            f"CV Folds: {self.cv_folds}, CV Seed: {self.cv_random_seed}, "
            f"Model Type: {self.model_type_enum.value}"
        )

    def _create_scorer(self):
        """Creates the scikit-learn scorer based on self.objective_metric_enum."""
        metric_enum = self.objective_metric_enum
        logger.debug(f"Creating scorer for metric: {metric_enum.value}")

        # For classification, most metrics are maximized.
        # If you add regression metrics later, this might need adjustment.
        greater_is_better = True

        try:
            if metric_enum == ObjectiveMetricEnum.F1_WEIGHTED:
                return make_scorer(
                    f1_score,
                    average="weighted",
                    zero_division=0,
                    greater_is_better=greater_is_better,
                )
            elif metric_enum == ObjectiveMetricEnum.AUC:
                return make_scorer(
                    roc_auc_score,
                    needs_proba=True,
                    average="weighted",
                    multi_class="ovr",
                    greater_is_better=greater_is_better,
                )
            elif metric_enum == ObjectiveMetricEnum.PRECISION_WEIGHTED:
                return make_scorer(
                    precision_score,
                    average="weighted",
                    zero_division=0,
                    greater_is_better=greater_is_better,
                )
            elif metric_enum == ObjectiveMetricEnum.RECALL_WEIGHTED:
                return make_scorer(
                    recall_score,
                    average="weighted",
                    zero_division=0,
                    greater_is_better=greater_is_better,
                )
            elif metric_enum == ObjectiveMetricEnum.ACCURACY:
                return make_scorer(accuracy_score, greater_is_better=greater_is_better)
            else:  # Should not happen due to enum validation
                logger.error(
                    f"Scorer creation: Unsupported metric enum '{metric_enum}'. This is a bug."
                )
                raise ValueError(f"Unsupported objective metric: {metric_enum.value}")
        except Exception as e:
            raise ValueError(
                f"Could not create scorer for metric '{metric_enum.value}'"
            ) from e

    def _suggest_hyperparameters(self, trial: Trial) -> Dict[str, Any]:
        """
        Suggests hyperparameters for the trial.
        Assumes self.hp_space_config contains dicts that have already passed
        HPSuggestion Pydantic validation.
        """
        suggested_params = {}
        logger.debug(
            f"Trial {trial.number}: Suggesting parameters from (pre-validated) hp_space_config..."
        )
        try:
            for (
                param_conf_data
            ) in self.hp_space_config:  # param_conf_data is a dict here
                name = param_conf_data["param_name"]
                # suggest_type is already validated and normalized by HPSuggestion's field_validator
                suggest_type = param_conf_data["suggest_type"]

                if suggest_type == "categorical":
                    # 'choices' is guaranteed to be valid and present by Pydantic HPSuggestion validation
                    choices_val = param_conf_data["choices"]
                    suggested_params[name] = trial.suggest_categorical(
                        name, choices_val
                    )
                elif suggest_type == "int":
                    # 'low', 'high' are guaranteed valid; 'step' is None or positive int
                    low_val = int(param_conf_data["low"])
                    high_val = int(param_conf_data["high"])
                    step_val = (
                        int(param_conf_data["step"])
                        if param_conf_data.get("step") is not None
                        else 1
                    )
                    log_val = param_conf_data.get("log", False)

                    suggested_params[name] = trial.suggest_int(
                        name, low_val, high_val, step=step_val, log=log_val
                    )
                elif suggest_type == "float":
                    # 'low', 'high' are guaranteed valid; 'step' is None or positive float
                    low_val = float(param_conf_data["low"])
                    high_val = float(param_conf_data["high"])
                    # Optuna's suggest_float takes step=None for continuous range.
                    step_val = (
                        float(param_conf_data["step"])
                        if param_conf_data.get("step") is not None
                        else None
                    )
                    log_val = param_conf_data.get("log", False)

                    suggested_params[name] = trial.suggest_float(
                        name, low_val, high_val, step=step_val, log=log_val
                    )
                # No 'else' needed as suggest_type should have been validated upstream by Pydantic

            logger.debug(
                f"Trial {trial.number}: Suggested Hyperparameters = {suggested_params}"
            )
            return suggested_params
        except (
            KeyError
        ) as ke:  # Catch if a validated field is unexpectedly missing (should not happen)
            logger.error(
                f"Trial {trial.number}: KeyError accessing validated HPSuggestion data: {ke}. This indicates an issue with upstream data consistency.",
                exc_info=True,
            )
            raise optuna.TrialPruned(
                f"Internal error accessing hyperparameter config: {ke}"
            ) from ke
        except Exception as e:  # Catch any other unexpected issues during suggestion
            logger.error(
                f"Trial {trial.number}: Error during Optuna suggestion phase: {e}",
                exc_info=True,
            )
            raise optuna.TrialPruned(f"Optuna suggestion failed: {e}") from e

    def __call__(self, trial: Trial) -> float:
        """Executed for each Optuna trial."""
        logger.info(
            f"--- Starting Optuna Trial {trial.number} for model {self.model_type_enum.value} ---"
        )
        try:
            suggested_hyperparams = self._suggest_hyperparameters(trial)
        except optuna.TrialPruned as prune_exc:
            logger.info(
                f"Trial {trial.number} pruned during parameter suggestion: {prune_exc}"
            )
            raise

        is_maximize = (
            getattr(self.scorer, "_sign", 1) > 0
        )  # Check scorer's optimization direction
        failed_value = 0.0 if is_maximize else float("inf")  # Value for failed trials
        metric_value = failed_value

        try:
            # Create a temporary model strategy for this trial
            # Pass the full base_job_config as job_config to the strategy
            # The strategy's _get_model_instance will use random_seed from this job_config
            temp_strategy = create_model_strategy(
                model_type=self.model_type_enum,
                model_config=suggested_hyperparams,  # Trial-specific HPs
                job_config=self.base_job_config,  # Overall job config for seeds, etc.
                artifact_service=self.artifact_service,
            )

            model_instance_for_cv = (
                temp_strategy._get_model_instance()
            )  # Get a fresh model with trial HPs

            logger.debug(
                f"Trial {trial.number}: Performing {self.cv_folds}-fold CV with {model_instance_for_cv.__class__.__name__}..."
            )

            # Cross-validation logic
            is_classification = (
                pd.api.types.is_integer_dtype(self.y) and self.y.nunique() >= 2
            )
            cv_splitter = None
            if is_classification:
                min_class_count = self.y.value_counts().min()
                actual_cv_folds = min(self.cv_folds, min_class_count)
                if actual_cv_folds < 2:
                    logger.warning(
                        f"Trial {trial.number}: Not enough samples in minority class for {self.cv_folds}-fold CV. Skipping CV for this trial."
                    )
                    trial.set_user_attr("cv_error", "Not enough samples for CV.")
                    return float(
                        failed_value
                    )  # Return failed_value if CV cannot be performed

                if actual_cv_folds < self.cv_folds:
                    logger.warning(
                        f"Trial {trial.number}: Reducing CV folds from {self.cv_folds} to {actual_cv_folds} due to class imbalance."
                    )

                cv_splitter = StratifiedKFold(
                    n_splits=actual_cv_folds,
                    shuffle=True,
                    random_state=self.cv_random_seed,
                )
            elif not is_classification:  # Regression or other task types
                logger.warning(
                    f"Trial {trial.number}: Target is not suitable for StratifiedKFold (not integer or single class). Using standard KFold or adapt as needed."
                )
                # For non-classification, or if stratification isn't appropriate, use KFold or other suitable CV.
                # from sklearn.model_selection import KFold
                # cv_splitter = KFold(n_splits=self.cv_folds, shuffle=True, random_state=self.cv_random_seed)
                # For now, let's raise if not classification, as defect prediction is typically classification
                trial.set_user_attr(
                    "cv_error",
                    "CV not performed for non-classification or problematic target.",
                )
                return float(failed_value)

            scores = cross_val_score(
                estimator=model_instance_for_cv,  # Use the model instance
                X=self.X,
                y=self.y,
                cv=cv_splitter,
                scoring=self.scorer,
                n_jobs=-1,  # Use all available cores for CV
                error_score="raise",  # Raise error if a fold fails
            )
            metric_value = np.mean(scores)
            trial.set_user_attr("cv_scores", scores.tolist())
            trial.set_user_attr(f"mean_cv_{self.objective_metric_str}", metric_value)
            logger.info(
                f"Trial {trial.number}: CV Scores ({self.objective_metric_str}) = {scores.tolist()}, Mean = {metric_value:.4f}"
            )

            trial.report(metric_value, step=0)  # Report after each trial for pruning
            if trial.should_prune():
                logger.info(f"Trial {trial.number}: Pruned by Optuna pruner.")
                raise optuna.TrialPruned()

        except optuna.TrialPruned:
            raise  # Re-raise to let Optuna handle it
        except ValueError as ve:  # Catch specific errors like single class in fold
            if "pos_label=1 is not a valid label" in str(
                ve
            ) or "Only one class present in y_true." in str(ve):
                logger.warning(
                    f"Trial {trial.number}: CV fold error (likely single class in a fold). Details: {ve}"
                )
                trial.set_user_attr(
                    "cv_error", "Fold contained only one class or invalid labels."
                )
            else:
                logger.error(
                    f"Trial {trial.number}: ValueError during evaluation: {ve}",
                    exc_info=True,
                )
                trial.set_user_attr("error", f"ValueError: {str(ve)}")
            metric_value = failed_value  # Ensure failed_value is assigned
        except Exception as e:
            logger.error(
                f"Trial {trial.number}: Failed during evaluation: {type(e).__name__}: {e}",
                exc_info=True,
            )
            trial.set_user_attr("error", f"{type(e).__name__}: {str(e)}")
            metric_value = failed_value  # Ensure failed_value is assigned

        logger.info(f"--- Finished Optuna Trial {trial.number} ---")
        if np.isnan(metric_value) or np.isinf(metric_value):
            logger.warning(
                f"Trial {trial.number}: Resulting metric is NaN/Inf. Returning failed value: {failed_value}"
            )
            return float(failed_value)
        return float(metric_value)
