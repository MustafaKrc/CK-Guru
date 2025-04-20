# worker/ml/services/hp_search_objective.py
import logging
from typing import Dict, Any, List

import optuna
import pandas as pd
from optuna.trial import Trial
from sklearn.model_selection import cross_val_score
from sklearn.metrics import make_scorer, f1_score

# Import necessary components
from .factories.strategy_factory import create_model_strategy
# Import base strategy for type hint if needed
# from .strategies.base_strategy import BaseModelStrategy

logger = logging.getLogger(__name__)

class Objective:
    """Wraps the objective function for Optuna study, used by HPSearchJobHandler."""

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
        self.model_type = base_job_config.get('model_type')
        if not self.model_type:
            raise ValueError("Objective requires 'model_type' in base_job_config")
        logger.debug("HP Search Objective initialized.")

    def __call__(self, trial: Trial) -> float:
        """
        Executes one trial of the hyperparameter search.

        Args:
            trial: An Optuna Trial object.

        Returns:
            The performance metric value (float) to be optimized.
        """
        logger.info(f"--- Starting Optuna Trial {trial.number} ---")
        # --- 1. Suggest Hyperparameters ---
        suggested_params: Dict[str, Any] = {}
        try:
            for param_conf in self.hp_space_config:
                name = param_conf['param_name']
                suggest_type = param_conf['suggest_type']
                low = param_conf.get('low')
                high = param_conf.get('high')
                step_val = param_conf.get('step')
                log = param_conf.get('log', False) # Default log to False
                choices = param_conf.get('choices')

                if suggest_type == 'categorical':
                    if choices is None: raise ValueError("'choices' required for categorical")
                    suggested_params[name] = trial.suggest_categorical(name, choices)
                elif suggest_type == 'int':
                    if low is None or high is None: raise ValueError("'low' and 'high' required for int")
                    if step_val is not None and not isinstance(step_val, int): step_val = int(step_val) # Ensure int
                    suggested_params[name] = trial.suggest_int(name, low, high, step=step_val or 1, log=log) # Default step=1 for int
                elif suggest_type == 'float':
                    if low is None or high is None: raise ValueError("'low' and 'high' required for float")
                    if step_val is not None and not isinstance(step_val, (int, float)): step_val = None # Ignore invalid step for float
                    suggested_params[name] = trial.suggest_float(name, low, high, step=step_val, log=log)
                else:
                    logger.warning(f"Trial {trial.number}: Unsupported suggest_type '{suggest_type}' for param '{name}'. Skipping.")
                    # Consider raising TrialPruned or returning worst score if essential param missing
        except Exception as e:
            logger.error(f"Trial {trial.number}: Error suggesting parameters: {e}", exc_info=True)
            # Pruning is a good option if parameter suggestion fails
            raise optuna.TrialPruned(f"Parameter suggestion failed: {e}")

        logger.info(f"Trial {trial.number}: Suggested Params = {suggested_params}")

        # --- 2. Instantiate Model/Strategy & Evaluate ---
        metric_value: float = 0.0 # Default value (assume higher is better)
        optimization_direction = self.base_job_config.get('optuna_config', {}).get('direction', 'maximize')
        failed_value = 0.0 if optimization_direction == 'maximize' else float('inf')

        try:
            # Create a temporary strategy instance with suggested params for this trial
            # Pass suggested_params as model_config, and base_job_config for other settings
            temp_strategy = create_model_strategy(self.model_type, suggested_params, self.base_job_config)
            # Get the unfitted model instance from the strategy
            # Assumes strategy classes have a method like _get_model_instance()
            model_instance = temp_strategy._get_model_instance()

            # --- Evaluation using Cross-Validation ---
            cv_folds = self.base_job_config.get('optuna_config', {}).get('hp_search_cv_folds', 3)
            # Weighted F1 over all present classes (no fixed pos_label)
            scorer = make_scorer(f1_score, average='weighted', zero_division=0)

            logger.debug(f"Trial {trial.number}: Performing {cv_folds}-fold CV...")
            scores = cross_val_score(model_instance, self.X, self.y, cv=cv_folds, scoring=scorer, n_jobs=-1) # Use parallelism
            metric_value = scores.mean()

            # Store additional info if needed
            trial.set_user_attr("cv_scores", scores.tolist())
            trial.set_user_attr("mean_cv_f1_weighted", metric_value)
            logger.info(f"Trial {trial.number}: CV F1 Scores = {scores.tolist()}, Mean = {metric_value:.4f}")

        except Exception as e:
            logger.error(f"Trial {trial.number}: Failed during model instantiation or evaluation: {e}", exc_info=True)
            metric_value = failed_value # Return worst score on failure
            # Optionally prune the trial if evaluation fails catastrophically
            # raise optuna.TrialPruned("Evaluation failed")

        logger.info(f"--- Finished Optuna Trial {trial.number} ---")
        return metric_value