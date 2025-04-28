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

# Import necessary components
from .factories.strategy_factory import create_model_strategy
# Import base strategy for type hint if needed
# from .strategies.base_strategy import BaseModelStrategy
from shared.schemas.hp_search_job import ObjectiveMetricEnum # Import the enum

logger = logging.getLogger(__name__)

class Objective:
    """
    Wraps the objective function for Optuna study.
    Responsible for:
    1. Suggesting hyperparameters based on the trial and configuration.
    2. Instantiating the model strategy with suggested parameters.
    3. Evaluating the model using cross-validation with the specified metric.
    4. Reporting the result to Optuna and handling pruning.
    """

    def __init__(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        hp_space_config: list,
        base_job_config: dict
    ):
        self.X = X
        self.y = y
        self.hp_space_config = hp_space_config
        self.base_job_config = base_job_config
        self.optuna_config = base_job_config.get('optuna_config', {})

        model_type_value = base_job_config.get('model_type') # Get the value (potentially string)
        if not model_type_value:
            raise ValueError("Objective requires 'model_type' in base_job_config")

        try:
            # Convert the value to the enum member
            self.model_type_enum = ModelTypeEnum(model_type_value)
        except ValueError:
            raise ValueError(f"Invalid 'model_type' value '{model_type_value}' found in base_job_config.")

        self.objective_metric = self.optuna_config.get('objective_metric', ObjectiveMetricEnum.F1_WEIGHTED.value)
        self.cv_folds = self.optuna_config.get('hp_search_cv_folds', 3)
        self.random_seed = base_job_config.get('random_seed', 42)
        self.scorer = self._create_scorer()

        logger.debug(
            f"HP Search Objective initialized. Metric: {self.objective_metric}, "
            f"CV Folds: {self.cv_folds}, Random Seed: {self.random_seed}, "
            f"Model Type: {self.model_type_enum.value}" # Log the stored enum value
        )
        
    def _create_scorer(self):
        """Creates the scikit-learn scorer based on the configured metric."""
        metric = self.objective_metric.lower()
        logger.debug(f"Creating scorer for metric: {metric}")

        # Determine if higher is better based on metric name
        maximize_metrics = {
            ObjectiveMetricEnum.F1_WEIGHTED.value,
            ObjectiveMetricEnum.AUC.value,
            ObjectiveMetricEnum.PRECISION_WEIGHTED.value,
            ObjectiveMetricEnum.RECALL_WEIGHTED.value,
            ObjectiveMetricEnum.ACCURACY.value
        }
        greater_is_better = metric in maximize_metrics

        try:
            # Use f1_score directly to set labels parameter if needed
            if metric == ObjectiveMetricEnum.F1_WEIGHTED.value:
                # When using average='weighted', labels parameter isn't strictly needed
                # but setting zero_division=0 handles cases where a class has no predictions/instances.
                return make_scorer(f1_score, average='weighted', zero_division=0, greater_is_better=greater_is_better)
            elif metric == ObjectiveMetricEnum.AUC.value:
                # AUC is less prone to this issue but needs probabilities
                return make_scorer(roc_auc_score, needs_proba=True, average='weighted', multi_class='ovr', greater_is_better=greater_is_better)
            elif metric == ObjectiveMetricEnum.PRECISION_WEIGHTED.value:
                return make_scorer(precision_score, average='weighted', zero_division=0, greater_is_better=greater_is_better)
            elif metric == ObjectiveMetricEnum.RECALL_WEIGHTED.value:
                return make_scorer(recall_score, average='weighted', zero_division=0, greater_is_better=greater_is_better)
            # --- END MODIFICATION ---
            elif metric == ObjectiveMetricEnum.ACCURACY.value:
                return make_scorer(accuracy_score, greater_is_better=greater_is_better)
            else:
                logger.warning(f"Unsupported objective_metric '{self.objective_metric}'. Defaulting to F1 Weighted.")
                self.objective_metric = ObjectiveMetricEnum.F1_WEIGHTED.value
                return make_scorer(f1_score, average='weighted', zero_division=0, greater_is_better=True)
        except Exception as e:
            logger.error(f"Failed to create scorer for metric '{metric}': {e}", exc_info=True)
            raise ValueError(f"Could not create scorer for metric '{metric}'") from e


    def _suggest_hyperparameters(self, trial: Trial) -> Dict[str, Any]:
        """Suggests hyperparameters for the current trial based on hp_space_config."""
        suggested_params = {}
        logger.debug(f"Trial {trial.number}: Suggesting parameters...")
        try:
            for param_conf in self.hp_space_config:
                name = param_conf['param_name']
                suggest_type = param_conf['suggest_type']
                low = param_conf.get('low')
                high = param_conf.get('high')
                step_val = param_conf.get('step')
                log = param_conf.get('log', False)
                choices = param_conf.get('choices')

                if suggest_type == 'categorical':
                    if choices is None: raise ValueError(f"'choices' required for categorical param '{name}'")
                    suggested_params[name] = trial.suggest_categorical(name, choices)
                elif suggest_type == 'int':
                    if low is None or high is None: raise ValueError(f"'low' and 'high' required for int param '{name}'")
                    # Ensure step is int if provided
                    if step_val is not None:
                        try: step_val = int(step_val)
                        except (ValueError, TypeError): step_val = 1; logger.warning(f"Invalid step '{param_conf.get('step')}' for int param '{name}', using 1.")
                    suggested_params[name] = trial.suggest_int(name, int(low), int(high), step=step_val or 1, log=log)
                elif suggest_type == 'float':
                    if low is None or high is None: raise ValueError(f"'low' and 'high' required for float param '{name}'")
                    # Step for float can be float or int, None if not provided
                    if step_val is not None and not isinstance(step_val, (int, float)):
                        step_val = None; logger.warning(f"Invalid step '{param_conf.get('step')}' for float param '{name}', ignoring step.")
                    suggested_params[name] = trial.suggest_float(name, float(low), float(high), step=step_val, log=log)
                else:
                    logger.warning(f"Trial {trial.number}: Unsupported suggest_type '{suggest_type}' for param '{name}'. Skipping.")
            logger.debug(f"Trial {trial.number}: Suggested Params = {suggested_params}")
            return suggested_params
        except Exception as e:
            logger.error(f"Trial {trial.number}: Error suggesting parameters: {e}", exc_info=True)
            # Pruning is appropriate if parameter suggestion fails, as the trial cannot proceed meaningfully.
            raise optuna.TrialPruned(f"Parameter suggestion failed: {e}") from e

    def __call__(self, trial: Trial) -> float:
        logger.info(f"--- Starting Optuna Trial {trial.number} ---")
        try:
            suggested_params = self._suggest_hyperparameters(trial)
        except optuna.TrialPruned as prune_exc:
            logger.info(f"Trial {trial.number} pruned during parameter suggestion: {prune_exc}")
            raise # Re-raise prune exceptions correctly

        is_maximize = getattr(self.scorer, '_sign', 1) > 0
        failed_value = 0.0 if is_maximize else float('inf') # Default to worst score on failure
        metric_value = failed_value

        try:
            # Use the stored model_type_enum
            trial_job_config = self.base_job_config.copy()
            temp_strategy = create_model_strategy(self.model_type_enum, suggested_params, trial_job_config)
            model_instance = temp_strategy._get_model_instance()

            logger.debug(f"Trial {trial.number}: Performing {self.cv_folds}-fold CV with scorer: {self.scorer}")
            is_classification_target = pd.api.types.is_integer_dtype(self.y) and self.y.nunique() < 20
            cv_splitter = None
            if is_classification_target and self.y.nunique() > 1: # Check if more than 1 class exists for stratification
                try:
                    # Ensure n_splits is not greater than the number of members in the smallest class
                    min_class_count = self.y.value_counts().min()
                    n_splits_adjusted = min(self.cv_folds, min_class_count)
                    if n_splits_adjusted < self.cv_folds:
                        logger.warning(f"Trial {trial.number}: Reducing CV folds from {self.cv_folds} to {n_splits_adjusted} due to small minority class size ({min_class_count}).")
                    if n_splits_adjusted >= 2: # Need at least 2 splits for CV
                        cv_splitter = StratifiedKFold(n_splits=n_splits_adjusted, shuffle=True, random_state=self.random_seed)
                        logger.debug(f"Using StratifiedKFold with {n_splits_adjusted} splits.")
                    else:
                        logger.warning(f"Trial {trial.number}: Cannot use StratifiedKFold with adjusted splits < 2. Skipping CV stratification.")
                except Exception as skf_err:
                    logger.warning(f"Trial {trial.number}: Error setting up StratifiedKFold ({skf_err}). Skipping CV stratification.")
            elif is_classification_target and self.y.nunique() <= 1:
                 logger.warning(f"Trial {trial.number}: Target variable has only one class. Skipping CV.")
                 # Handle single class case: score is undefined or trivial (e.g., 1.0 accuracy)
                 # Return a default value or handle based on metric
                 # For F1 weighted on a single class, the score is often 1.0 if predicted correctly, 0 otherwise.
                 # Let's return the 'failed_value' to indicate CV couldn't run meaningfully.
                 trial.set_user_attr("warning", "Single class in target variable, CV skipped.")
                 logger.info(f"--- Finished Optuna Trial {trial.number} (Skipped CV) ---")
                 return float(failed_value) # Return worst score as CV didn't run

            # Perform Cross Validation
            scores = cross_val_score(
                model_instance, self.X, self.y,
                cv=cv_splitter, # Pass the potentially adjusted splitter
                scoring=self.scorer,
                n_jobs=1, # Set n_jobs=1 because of the loky warning
                error_score='raise'
            )
            metric_value = np.mean(scores)

            trial.set_user_attr("cv_scores", scores.tolist())
            trial.set_user_attr(f"mean_cv_{self.objective_metric}", metric_value)
            logger.info(f"Trial {trial.number}: CV Scores ({self.objective_metric}) = {scores.tolist()}, Mean = {metric_value:.4f}")

            # Pruning check
            trial.report(metric_value, step=0)
            if trial.should_prune():
                 logger.info(f"Trial {trial.number}: Pruned by {self.optuna_config.get('pruner_type', 'default pruner')}.")
                 raise optuna.TrialPruned()

        except optuna.TrialPruned:
            raise # Re-raise prune exceptions
        except ValueError as ve:
             # Catch the specific pos_label error, log it, and return the failed value
             if "pos_label=1 is not a valid label" in str(ve):
                 logger.warning(f"Trial {trial.number}: CV failed because a fold contained only class 0. Details: {ve}")
                 trial.set_user_attr("cv_error", "Fold contained only negative class.")
                 metric_value = failed_value # Assign worst score
             else:
                 # Handle other ValueErrors
                 logger.error(f"Trial {trial.number}: ValueError during model instantiation or CV evaluation: {ve}", exc_info=True)
                 trial.set_user_attr("error", f"ValueError: {str(ve)}")
                 metric_value = failed_value
        except Exception as e:
            logger.error(f"Trial {trial.number}: Failed during model instantiation or CV evaluation: {e}", exc_info=True)
            trial.set_user_attr("error", f"{type(e).__name__}: {str(e)}")
            metric_value = failed_value # Assign worst score on other errors too

        logger.info(f"--- Finished Optuna Trial {trial.number} ---")
        if np.isnan(metric_value) or np.isinf(metric_value):
            logger.warning(f"Trial {trial.number}: Metric value is NaN or Inf. Returning failed value: {failed_value}")
            return float(failed_value)
        return float(metric_value)