# worker/ml/services/hp_search_objective.py
import logging
from typing import Dict, Any, List

import optuna
import pandas as pd
import numpy as np
from optuna.trial import Trial
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import make_scorer, f1_score, roc_auc_score, precision_score, recall_score, accuracy_score

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
        hp_space_config: list,      # List of dicts defining the search space
        base_job_config: dict       # Base config (model_type, seed, etc.) passed from handler
    ):
        self.X = X
        self.y = y
        self.hp_space_config = hp_space_config
        self.base_job_config = base_job_config
        self.optuna_config = base_job_config.get('optuna_config', {})
        self.model_type = base_job_config.get('model_type')
        if not self.model_type:
            raise ValueError("Objective requires 'model_type' in base_job_config")

        # Store metric and CV folds, create scorer
        self.objective_metric = self.optuna_config.get('objective_metric', ObjectiveMetricEnum.F1_WEIGHTED.value)
        self.cv_folds = self.optuna_config.get('hp_search_cv_folds', 3)
        self.random_seed = base_job_config.get('random_seed', 42)
        self.scorer = self._create_scorer() # Create scorer once during initialization

        logger.debug(
            f"HP Search Objective initialized. Metric: {self.objective_metric}, "
            f"CV Folds: {self.cv_folds}, Random Seed: {self.random_seed}"
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
            if metric == ObjectiveMetricEnum.F1_WEIGHTED.value:
                return make_scorer(f1_score, average='weighted', zero_division=0, greater_is_better=greater_is_better)
            elif metric == ObjectiveMetricEnum.AUC.value:
                # AUC needs probabilities and careful handling of multi-class
                return make_scorer(roc_auc_score, needs_proba=True, average='weighted', multi_class='ovr', greater_is_better=greater_is_better)
            elif metric == ObjectiveMetricEnum.PRECISION_WEIGHTED.value:
                return make_scorer(precision_score, average='weighted', zero_division=0, greater_is_better=greater_is_better)
            elif metric == ObjectiveMetricEnum.RECALL_WEIGHTED.value:
                return make_scorer(recall_score, average='weighted', zero_division=0, greater_is_better=greater_is_better)
            elif metric == ObjectiveMetricEnum.ACCURACY.value:
                return make_scorer(accuracy_score, greater_is_better=greater_is_better)
            # Add other metrics here
            else:
                logger.warning(f"Unsupported objective_metric '{self.objective_metric}'. Defaulting to F1 Weighted.")
                self.objective_metric = ObjectiveMetricEnum.F1_WEIGHTED.value # Correct the metric name
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
        """Executes one trial: suggests params, creates model, evaluates with CV."""
        logger.info(f"--- Starting Optuna Trial {trial.number} ---")
        suggested_params = self._suggest_hyperparameters(trial) # Handles prune on suggestion error

        # --- Determine failure value based on optimization direction ---
        # Use the created scorer's knowledge of whether higher is better
        is_maximize = getattr(self.scorer, '_sign', 1) > 0 # Scorer sign is 1 if higher is better
        failed_value = 0.0 if is_maximize else float('inf')
        metric_value = failed_value # Default to failed value

        try:
            # Create a strategy instance with suggested params for this trial
            # Merge suggested params with base job config (e.g., random_seed) for the strategy
            trial_job_config = self.base_job_config.copy()
            # model_config for strategy is just the suggested hyperparams
            temp_strategy = create_model_strategy(self.model_type, suggested_params, trial_job_config)
            model_instance = temp_strategy._get_model_instance() # Get the unfitted sklearn model etc.

            # --- Evaluation using Cross-Validation ---
            logger.debug(f"Trial {trial.number}: Performing {self.cv_folds}-fold CV with scorer: {self.scorer}")
            # Use StratifiedKFold for classification tasks if target is suitable
            # Check if target looks like classification labels (e.g., few unique integer values)
            is_classification_target = pd.api.types.is_integer_dtype(self.y) and self.y.nunique() < 20 # Heuristic
            cv_splitter = None
            if is_classification_target:
                cv_splitter = StratifiedKFold(n_splits=self.cv_folds, shuffle=True, random_state=self.random_seed)
                logger.debug("Using StratifiedKFold for CV.")
            else:
                # Use standard KFold or let cross_val_score decide if None
                # cv_splitter = KFold(n_splits=self.cv_folds, shuffle=True, random_state=self.random_seed)
                logger.debug("Using default KFold (or model-specific CV if applicable) for CV.")


            scores = cross_val_score(
                model_instance, self.X, self.y,
                cv=cv_splitter, # Pass the splitter
                scoring=self.scorer,
                n_jobs=-1, # Use available cores
                error_score='raise' # Raise error if a fold fails
            )
            metric_value = np.mean(scores) # Use numpy mean for robustness

            trial.set_user_attr("cv_scores", scores.tolist())
            trial.set_user_attr(f"mean_cv_{self.objective_metric}", metric_value) # Store with metric name
            logger.info(f"Trial {trial.number}: CV Scores ({self.objective_metric}) = {scores.tolist()}, Mean = {metric_value:.4f}")

            # --- Optuna Pruning Integration ---
            # Report the intermediate value (mean CV score) to the pruner
            trial.report(metric_value, step=0) # Use step=0 as CV is a single evaluation step here
            if trial.should_prune():
                 logger.info(f"Trial {trial.number}: Pruned by {self.optuna_config.get('pruner_type', 'default pruner')}.")
                 raise optuna.TrialPruned()

        except optuna.TrialPruned:
            raise # Re-raise prune exceptions correctly
        except Exception as e:
            logger.error(f"Trial {trial.number}: Failed during model instantiation or CV evaluation: {e}", exc_info=True)
            metric_value = failed_value # Return worst score on failure
            # Optionally store the error in user attrs for debugging
            trial.set_user_attr("error", f"{type(e).__name__}: {str(e)}")


        logger.info(f"--- Finished Optuna Trial {trial.number} ---")
        # Ensure we return a float, handle potential NaN/Inf from mean calculation
        if np.isnan(metric_value) or np.isinf(metric_value):
            logger.warning(f"Trial {trial.number}: Metric value is NaN or Inf. Returning failed value: {failed_value}")
            return float(failed_value) # Ensure float type
        return float(metric_value) # Ensure float type