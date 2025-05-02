# worker/ml/services/strategies/shap_strategy.py
import logging
import pandas as pd
import numpy as np
from typing import Optional, List, Any

try:
    import shap
except ImportError:
    shap = None # Handle optional dependency

from .base_xai_strategy import BaseXAIStrategy
from shared.schemas.xai import SHAPResultData, InstanceSHAPResult, FeatureSHAPValue

logger = logging.getLogger(__name__)

class SHAPStrategy(BaseXAIStrategy):
    """Generates SHAP explanations."""

    def explain(self, X_inference: pd.DataFrame, identifiers_df: pd.DataFrame) -> Optional[SHAPResultData]:
        if shap is None:
            logger.error("SHAP library is not installed. Cannot generate SHAP explanations.")
            return None
        if X_inference.empty:
                logger.warning("SHAPStrategy: Input DataFrame is empty. No explanations generated.")
                return None

        logger.info(f"Generating SHAP explanations for {len(X_inference)} instances...")
        try:
            # TODO: Make explainer selection more dynamic based on model type
            # Assuming TreeExplainer for now, suitable for tree-based models
            if not hasattr(self.model, 'predict'): # Basic check
                    raise TypeError("Model does not have a predict method suitable for SHAP.")
            # TreeExplainer is often efficient for tree models
            try:
                explainer = shap.TreeExplainer(self.model)
                # SHAP values often returned as list (for multi-class) or single array
                shap_values_raw = explainer.shap_values(X_inference)

                shap_values_pos_class = shap_values_raw[:, :, 1]

            except Exception as tree_explainer_err:
                    logger.warning(f"TreeExplainer failed ({tree_explainer_err}). Trying KernelExplainer (slower).")
                    if self.background_data is None or self.background_data.empty:
                        logger.warning("KernelExplainer needs background data. Sampling from inference data.")
                        # Use shap.sample to select representative background samples
                        background_sample = shap.sample(X_inference, min(100, X_inference.shape[0]))
                    else:
                        background_sample = self.background_data
                        if len(background_sample) > 100: # Limit background size for KernelExplainer
                            background_sample = shap.sample(background_sample, 100)

                    # KernelExplainer needs predict_proba
                    if not hasattr(self.model, 'predict_proba'):
                        raise TypeError("Model needs predict_proba for KernelExplainer.")
                    explainer = shap.KernelExplainer(self.model.predict_proba, background_sample)
                    # Need to specify link='logit' usually for probabilities
                    shap_values_raw = explainer.shap_values(X_inference, nsamples='auto')[1] # Explain class 1 prob
                    shap_values_pos_class = shap_values_raw

            instance_results: List[InstanceSHAPResult] = []
            feature_names = X_inference.columns.tolist()

            for i in range(len(identifiers_df)):
                instance_id_row = identifiers_df.iloc[i]
                shap_values_for_instance = shap_values_pos_class[i]
                # Ensure correct number of SHAP values matches features
                if len(shap_values_for_instance) != len(feature_names):
                        logger.error(f"SHAP value count mismatch for instance {i}. Expected {len(feature_names)}, got {len(shap_values_for_instance)}. Skipping instance.")
                        continue
                

                instance_list: List[FeatureSHAPValue] = []  
                for idx, (fn, sv) in enumerate(zip(feature_names, shap_values_for_instance)):

                    instance_list.append(
                        FeatureSHAPValue(
                            feature=fn,
                            value=round(float(sv), 4),
                            feature_value=float(X_inference.iloc[i, idx])
                        )
                    )
                # Base value might be available depending on explainer type
                base_value = getattr(explainer, 'expected_value', None)
                # Adjust base value format if needed (e.g., index [1] for binary class 1)
                if isinstance(base_value, (list, np.ndarray)) and len(base_value)>1:
                    base_value_float = float(base_value[1]) if len(base_value)>1 else float(base_value[0])
                elif isinstance(base_value, (float, np.float_)):
                        base_value_float = float(base_value)
                else:
                        base_value_float = None


                instance_results.append(InstanceSHAPResult(
                    file=instance_id_row.get('file'),
                    class_name=instance_id_row.get('class_name'), # Use actual column name
                    shap_values=instance_list,
                    base_value = base_value_float
                ))

            if not instance_results:
                    logger.warning("SHAP explanation generated no valid instance results.")
                    return None

            return SHAPResultData(instance_shap_values=instance_results)

        except Exception as e:
            logger.error(f"Error generating SHAP explanation: {e}", exc_info=True)
            return None