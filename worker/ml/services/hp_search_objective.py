# worker/ml/services/hp_search_objective.py
import logging
from typing import Dict, Any, List

import optuna
import pandas as pd
import numpy as np
from optuna.trial import Trial
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import make_scorer, f1_score, roc_auc_score, precision_score, recall_score, accuracy_score

from shared.schemas.enums import ModelTypeEnum
from shared.schemas.hp_search_job import ObjectiveMetricEnum

from .factories.model_strategy_factory import create_model_strategy
from services.interfaces import IArtifactService

logger = logging.getLogger(__name__)

class Objective:
    """Wraps the objective function for Optuna study."""

    def __init__(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        hp_space_config: list,
        base_job_config: dict,
        artifact_service: IArtifactService # Add artifact_service parameter (use Interface)
    ):
        self.X = X
        self.y = y
        self.hp_space_config = hp_space_config
        self.base_job_config = base_job_config
        # Store the injected artifact service
        self.artifact_service: IArtifactService = artifact_service
        self.optuna_config = base_job_config.get('optuna_config', {})

        # --- Model Type Enum Handling (remains the same) ---
        model_type_value = base_job_config.get('model_type')
        if not model_type_value:
            raise ValueError("Objective requires 'model_type'")
        try:
            self.model_type_enum = ModelTypeEnum(model_type_value)
        except ValueError:
            raise ValueError(f"Invalid 'model_type' value '{model_type_value}'.")

        self.objective_metric = self.optuna_config.get('objective_metric', ObjectiveMetricEnum.F1_WEIGHTED.value)
        self.cv_folds = self.optuna_config.get('hp_search_cv_folds', 3)
        self.random_seed = base_job_config.get('random_seed', 42)
        self.scorer = self._create_scorer()

        logger.debug(
            f"HP Search Objective initialized. Metric: {self.objective_metric}, "
            f"CV Folds: {self.cv_folds}, Seed: {self.random_seed}, "
            f"Model Type: {self.model_type_enum.value}"
        )

    def _create_scorer(self):
        """Creates the scikit-learn scorer."""
        # --- Logic remains the same ---
        metric = self.objective_metric.lower()
        logger.debug(f"Creating scorer for metric: {metric}")
        maximize_metrics = { m.value for m in ObjectiveMetricEnum }
        greater_is_better = metric in maximize_metrics

        try:
            if metric == ObjectiveMetricEnum.F1_WEIGHTED.value:
                return make_scorer(f1_score, average='weighted', zero_division=0, greater_is_better=greater_is_better)
            elif metric == ObjectiveMetricEnum.AUC.value:
                return make_scorer(roc_auc_score, needs_proba=True, average='weighted', multi_class='ovr', greater_is_better=greater_is_better)
            elif metric == ObjectiveMetricEnum.PRECISION_WEIGHTED.value:
                return make_scorer(precision_score, average='weighted', zero_division=0, greater_is_better=greater_is_better)
            elif metric == ObjectiveMetricEnum.RECALL_WEIGHTED.value:
                return make_scorer(recall_score, average='weighted', zero_division=0, greater_is_better=greater_is_better)
            elif metric == ObjectiveMetricEnum.ACCURACY.value:
                return make_scorer(accuracy_score, greater_is_better=greater_is_better)
            else:
                logger.warning(f"Unsupported metric '{self.objective_metric}'. Defaulting to F1 Weighted.")
                self.objective_metric = ObjectiveMetricEnum.F1_WEIGHTED.value
                return make_scorer(f1_score, average='weighted', zero_division=0, greater_is_better=True)
        except Exception as e:
            raise ValueError(f"Could not create scorer for metric '{metric}'") from e


    def _suggest_hyperparameters(self, trial: Trial) -> Dict[str, Any]:
        """Suggests hyperparameters for the trial."""
        # --- Logic remains the same ---
        suggested_params = {}
        logger.debug(f"Trial {trial.number}: Suggesting parameters...")
        try:
            for param_conf in self.hp_space_config:
                name = param_conf['param_name']
                suggest_type = param_conf['suggest_type']
                # ... (rest of suggestion logic) ...
                if suggest_type == 'categorical':
                    choices = param_conf.get('choices')
                    if choices is None: raise ValueError(f"'choices' required for '{name}'")
                    suggested_params[name] = trial.suggest_categorical(name, choices)
                elif suggest_type == 'int':
                    low, high = param_conf.get('low'), param_conf.get('high')
                    if low is None or high is None: raise ValueError(f"'low'/'high' required for '{name}'")
                    step = param_conf.get('step'); log = param_conf.get('log', False)
                    if step is not None: step = int(step)
                    suggested_params[name] = trial.suggest_int(name, int(low), int(high), step=step or 1, log=log)
                elif suggest_type == 'float':
                    low, high = param_conf.get('low'), param_conf.get('high')
                    if low is None or high is None: raise ValueError(f"'low'/'high' required for '{name}'")
                    step = param_conf.get('step'); log = param_conf.get('log', False)
                    if step is not None and not isinstance(step, (int, float)): step = None
                    suggested_params[name] = trial.suggest_float(name, float(low), float(high), step=step, log=log)
                else: logger.warning(f"Unsupported suggest_type '{suggest_type}' for '{name}'. Skipping.")
            logger.debug(f"Trial {trial.number}: Suggested Params = {suggested_params}")
            return suggested_params
        except Exception as e:
            logger.error(f"Trial {trial.number}: Error suggesting parameters: {e}", exc_info=True)
            raise optuna.TrialPruned(f"Param suggestion failed: {e}") from e

    def __call__(self, trial: Trial) -> float:
        """Executed for each Optuna trial."""
        logger.info(f"--- Starting Optuna Trial {trial.number} ---")
        try:
            suggested_params = self._suggest_hyperparameters(trial)
        except optuna.TrialPruned as prune_exc:
            logger.info(f"Trial {trial.number} pruned during parameter suggestion: {prune_exc}")
            raise # Re-raise prune exceptions

        is_maximize = getattr(self.scorer, '_sign', 1) > 0
        failed_value = 0.0 if is_maximize else float('inf')
        metric_value = failed_value

        try:
            # --- Pass self.artifact_service to the factory ---
            temp_strategy = create_model_strategy(
                self.model_type_enum,
                suggested_params,
                self.base_job_config,
                self.artifact_service # Pass the stored artifact service
            )
            model_instance = temp_strategy._get_model_instance()

            # --- CV Logic (remains the same) ---
            logger.debug(f"Trial {trial.number}: Performing {self.cv_folds}-fold CV...")
            is_classification = pd.api.types.is_integer_dtype(self.y) and self.y.nunique() < 20
            cv_splitter = None
            if is_classification and self.y.nunique() > 1:
                try:
                    min_class_count = self.y.value_counts().min()
                    n_splits = min(self.cv_folds, min_class_count)
                    if n_splits < self.cv_folds: logger.warning(f"Trial {trial.number}: Reducing CV folds to {n_splits}.")
                    if n_splits >= 2: cv_splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=self.random_seed)
                    else: logger.warning(f"Trial {trial.number}: Cannot use StratifiedKFold (splits < 2).")
                except Exception as skf_err: logger.warning(f"Trial {trial.number}: Error setting up StratifiedKFold ({skf_err}).")
            elif is_classification: logger.warning(f"Trial {trial.number}: Single class target. Skipping CV.")
            # ... (Handle single class case - return failed_value) ...
            if is_classification and self.y.nunique() <= 1:
                trial.set_user_attr("warning", "Single class target, CV skipped.")
                logger.info(f"--- Finished Trial {trial.number} (Skipped CV) ---")
                return float(failed_value)

            scores = cross_val_score(model_instance, self.X, self.y, cv=cv_splitter, scoring=self.scorer, n_jobs=1, error_score='raise')
            metric_value = np.mean(scores)
            trial.set_user_attr("cv_scores", scores.tolist())
            trial.set_user_attr(f"mean_cv_{self.objective_metric}", metric_value)
            logger.info(f"Trial {trial.number}: CV Scores ({self.objective_metric}) = {scores.tolist()}, Mean = {metric_value:.4f}")

            # Pruning check
            trial.report(metric_value, step=0)
            if trial.should_prune():
                 logger.info(f"Trial {trial.number}: Pruned by {self.optuna_config.get('pruner_type', 'pruner')}.")
                 raise optuna.TrialPruned()

        except optuna.TrialPruned: raise # Re-raise
        except ValueError as ve:
             if "pos_label=1 is not a valid label" in str(ve):
                 logger.warning(f"Trial {trial.number}: CV failed (fold had only class 0). Details: {ve}")
                 trial.set_user_attr("cv_error", "Fold contained only negative class.")
             else: logger.error(f"Trial {trial.number}: ValueError: {ve}", exc_info=True); trial.set_user_attr("error", f"ValueError: {str(ve)}")
             metric_value = failed_value
        except Exception as e:
            logger.error(f"Trial {trial.number}: Failed eval: {e}", exc_info=True); trial.set_user_attr("error", f"{type(e).__name__}: {str(e)}")
            metric_value = failed_value

        logger.info(f"--- Finished Optuna Trial {trial.number} ---")
        if np.isnan(metric_value) or np.isinf(metric_value):
            logger.warning(f"Trial {trial.number}: Metric is NaN/Inf. Returning failed value: {failed_value}")
            return float(failed_value)
        return float(metric_value)