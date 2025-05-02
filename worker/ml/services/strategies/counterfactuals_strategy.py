# worker/ml/services/strategies/counterfactuals_strategy.py
import logging
import pandas as pd
import numpy as np
from typing import Optional, List, Any, Dict

try:
    import dice_ml
    DICE_AVAILABLE = True
except ImportError:
    dice_ml = None
    DICE_AVAILABLE = False

from .base_xai_strategy import BaseXAIStrategy
from shared.schemas.xai import (
    CounterfactualResultData, InstanceCounterfactualResult, CounterfactualExample
)

logger = logging.getLogger(__name__)

class CounterfactualsStrategy(BaseXAIStrategy):
    """Generates Counterfactual Explanations using DiCE."""

    def explain(self, X_inference: pd.DataFrame, identifiers_df: pd.DataFrame) -> Optional[CounterfactualResultData]:
        if not DICE_AVAILABLE:
            logger.error("DiCE-ML library is not installed. Cannot generate Counterfactual explanations.")
            return None
        if X_inference.empty:
            logger.warning("CounterfactualsStrategy: Input DataFrame is empty.")
            return None
        if not hasattr(self.model, 'predict'):
             logger.error("CounterfactualsStrategy: Model requires a 'predict' method.")
             return None
        # DiCE typically needs predict_proba as well for some methods/backends
        if not hasattr(self.model, 'predict_proba'):
              logger.warning("CounterfactualsStrategy: Model lacks 'predict_proba'. DiCE functionality might be limited.")
              # Proceed cautiously, DiCE might work with just predict for some methods

        logger.info(f"Generating Counterfactual explanations for {len(X_inference)} instances...")
        feature_names = X_inference.columns.tolist()
        cf_instance_results: List[InstanceCounterfactualResult] = []

        try:
            # --- Prepare Data ---
            y_pred_inference = self.model.predict(X_inference)
            # --- CONSISTENT OUTCOME NAME ---
            # TODO:
            # Get a consistent name for the outcome column
            outcome_col_name = 'is_buggy' # Define consistently
            data_for_dice = X_inference.copy()
            data_for_dice[outcome_col_name] = y_pred_inference # Add prediction with this name
            # --- END CONSISTENT OUTCOME NAME ---

            # Determine background dataframe for DiCE
            dice_dataframe = self.background_data
            if dice_dataframe is None or dice_dataframe.empty:
                logger.warning("Counterfactuals: Using inference data + predictions for DiCE Data object.")
                dice_dataframe = data_for_dice # Fallback uses inference + predictions
            else:
                # If using background data, ensure it has the target column (or handle appropriately)
                if outcome_col_name not in dice_dataframe.columns:
                    # This is tricky. Background data *should* ideally have the TRUE target.
                    # If not, DiCE might behave unexpectedly. Adding predicted target might be wrong.
                    # Let's add a placeholder and warn heavily.
                    logger.warning(f"Counterfactuals: Background data missing outcome column '{outcome_col_name}'. Adding placeholder (0). DiCE results might be affected.")
                    dice_dataframe = dice_dataframe.copy() # Avoid modifying original background_data
                    dice_dataframe[outcome_col_name] = 0

            # Define continuous features (assuming all for now)
            continuous_features = feature_names

            # Create DiCE Data object
            d = dice_ml.Data(dataframe=dice_dataframe,
                             continuous_features=continuous_features,
                             outcome_name=outcome_col_name) # Use consistent name

            # Create DiCE Model object
            m = dice_ml.Model(model=self.model, backend='sklearn', model_type='classifier') # Assuming sklearn

            # Initialize DiCE Explainer
            exp = dice_ml.Dice(d, m, method='random')

            # Generate Counterfactuals only for instances predicted as 1 (defect-prone)
            indices_to_explain = X_inference.index[y_pred_inference == 1]

            if len(indices_to_explain) == 0:
                # ... (handle no instances to explain) ...
                return CounterfactualResultData(instance_counterfactuals=[])

            logger.info(f"Attempting counterfactuals for {len(indices_to_explain)} instances...")
            num_cfs_per_instance = 3

            for i in indices_to_explain:
                instance_id_row = identifiers_df.iloc[i]
                # Query instance must NOT contain the outcome column
                query_instance = X_inference.loc[[i]] # Only features

                try:
                    # Generate CFs targeting class 0
                    dice_exp_results = exp.generate_counterfactuals(
                        query_instance, total_CFs=num_cfs_per_instance, desired_class=0
                    )

                    cf_examples_structured: List[CounterfactualExample] = []
                    if dice_exp_results and dice_exp_results.cf_examples_list:
                        for cf_example in dice_exp_results.cf_examples_list:
                            cf_df = cf_example.final_cfs_df
                            if cf_df is not None and not cf_df.empty:
                                # Extract features (make sure these match model's expected features)
                                cf_features_dict = cf_df.iloc[0][feature_names].to_dict()
                                # Predict probability of desired class (0) using *original* model
                                cf_prob_vector = self.model.predict_proba(pd.DataFrame([cf_features_dict]))[0]
                                cf_prob_desired_class = float(cf_prob_vector[0])

                                cf_examples_structured.append(CounterfactualExample(
                                    features=cf_features_dict,
                                    outcome_probability=round(cf_prob_desired_class, 4)
                                ))
                            else: logger.warning(f"DiCE returned empty CF DataFrame instance {i}.")

                    if cf_examples_structured:
                        cf_instance_results.append(InstanceCounterfactualResult(
                            file=instance_id_row.get('file'),
                            class_name=instance_id_row.get('class_name'),
                            counterfactuals=cf_examples_structured
                        ))
                    else: logger.warning(f"No CF examples found for instance {i}.")

                except KeyError as ke:
                     # Catch the specific KeyError if it persists after naming consistency check
                     logger.error(f"Counterfactual generation failed for instance {i} due to KeyError: {ke}. This might indicate DiCE expecting the outcome column in the query instance or a mismatch in feature names.", exc_info=False)
                     # Skip this instance
                except Exception as cf_instance_err:
                     logger.error(f"Counterfactual generation failed for instance {i}: {cf_instance_err}", exc_info=True)

            logger.info(f"Finished generating counterfactuals. Found examples for {len(cf_instance_results)} instances.")
            return CounterfactualResultData(instance_counterfactuals=cf_instance_results)

        except Exception as e:
            logger.error(f"Error generating Counterfactual explanation: {e}", exc_info=True)
            return None