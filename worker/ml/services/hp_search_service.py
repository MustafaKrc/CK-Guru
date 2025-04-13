# worker/ml/services/hp_search_service.py
import logging
from typing import Dict, Any

import optuna
import pandas as pd
from optuna.trial import Trial # More specific type hint
from sklearn.model_selection import cross_val_score # Example using CV for objective
from sklearn.metrics import make_scorer, f1_score # Example metric

from shared.core.config import settings

# Import necessary components from training_service
from .training_service import get_trainer, BaseModelTrainer, TrainResult

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper()) # Assuming settings accessible

class Objective:
    """Wraps the objective function for Optuna study."""

    def __init__(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        hp_space_config: list, # List of HPSuggestion schemas/dicts
        base_job_config: dict, # Base config (model_type, seed, etc.)
        # Add dataset_id or other context if needed by trainer init directly
    ):
        self.X = X
        self.y = y
        self.hp_space_config = hp_space_config
        self.base_job_config = base_job_config
        self.model_type = base_job_config.get('model_type', 'default_model')

    def __call__(self, trial: Trial) -> float:
        """
        Optuna objective function.

        Args:
            trial: An Optuna Trial object used to suggest hyperparameters.

        Returns:
            The performance metric value to be optimized (e.g., F1 score).
        """
        # --- 1. Suggest Hyperparameters ---
        suggested_params = {}
        for param_config in self.hp_space_config:
            name = param_config['param_name']
            suggest_type = param_config['suggest_type']
            # --- Get common parameters first ---
            low = param_config.get('low')
            high = param_config.get('high')
            step_val = param_config.get('step') # Get step here
            is_log = param_config.get('log', False)
            choices = param_config.get('choices')
            try:
                if suggest_type == 'categorical':
                    if choices is None: raise ValueError("Choices must be provided for categorical.")
                    suggested_params[name] = trial.suggest_categorical(name, choices)
                elif suggest_type == 'int':
                    if low is None or high is None: raise ValueError("low and high must be provided for int.")
                    # --- Check step_val AFTER getting it ---
                    if not isinstance(step_val, int) or step_val < 1:
                        step_val = 1 # Default step for int if invalid/None
                    # -----------------------------------------
                    suggested_params[name] = trial.suggest_int(name, low, high, step=step_val, log=is_log)
                elif suggest_type == 'float':
                    if low is None or high is None: raise ValueError("low and high must be provided for float.")
                    # step_val can be None for float, suggest_float handles it
                    suggested_params[name] = trial.suggest_float(name, low, high, step=step_val, log=is_log)
                else:
                    logger.warning(f"Unsupported suggestion type '{suggest_type}' for param '{name}'. Skipping.")
            except Exception as e:
                logger.error(f"Error suggesting parameter '{name}' ({suggest_type}): {e}", exc_info=True)
                raise optuna.TrialPruned(f"Failed to suggest parameter {name}") from e
                # Decide how to handle: raise, return default, or skip? Let's skip.
                # raise # Or re-raise to fail the trial

        logger.info(f"Trial {trial.number}: Suggested Params: {suggested_params}")

        # --- 2. Train and Evaluate Model ---
        # Create a specific job config for this trial, merging base + suggested params
        trial_job_config = self.base_job_config.copy()
        # trial_job_config['hyperparameters'] = suggested_params # Pass params separately

        try:
            # Instantiate trainer with suggested parameters for this trial
            trainer = get_trainer(self.model_type, suggested_params, trial_job_config)

            # --- Evaluation Strategy ---
            # Option A: Simple Train/Test split (like in training_service - less robust for HP search)
            # train_result = trainer.train(self.X, self.y) # train already does split/eval
            # metrics = train_result.metrics

            # Option B: Cross-validation (More robust for HP search)
            # Note: We need the *model instance* before fitting for cross_val_score
            model_instance = trainer._init_model() # Get the un-fitted model
            # Define scoring metric (e.g., weighted F1)
            # Note: Ensure y is compatible (e.g., for classification)
            # Explicitly set pos_label assuming True is the positive class
            scorer = make_scorer(f1_score, pos_label=True, average='weighted', zero_division=0)
            # Perform cross-validation
            # Adjust cv based on config or data size
            cv = trial_job_config.get('hp_search_cv_folds', 3)
            scores = cross_val_score(model_instance, self.X, self.y, cv=cv, scoring=scorer, n_jobs=-1) # Use multiple cores if available
            metric_value = scores.mean() # Use the average score across folds
            logger.info(f"Trial {trial.number}: CV F1 Scores: {scores}, Mean: {metric_value:.4f}")

            # Store CV score or other relevant info as user attributes if desired
            trial.set_user_attr("cv_scores", scores.tolist())
            trial.set_user_attr("mean_cv_f1_weighted", metric_value)

        except Exception as e:
            logger.error(f"Trial {trial.number}: Failed during training/evaluation: {e}", exc_info=True)
            # Returning a very bad score or raising optuna.TrialPruned might be appropriate
            # Returning 0.0 assumes higher is better and this trial failed badly.
            # Check Optuna docs for best practices on handling exceptions.
            # For now, return 0.0 assuming maximization. Adjust if minimizing.
            # If minimizing, return float('inf').
            optimization_direction = self.base_job_config.get('optuna_config', {}).get('direction', 'maximize')
            return 0.0 if optimization_direction == 'maximize' else float('inf')


        # --- 3. Return the metric Optuna should optimize ---
        # Example: Return the mean F1 score from cross-validation
        return metric_value