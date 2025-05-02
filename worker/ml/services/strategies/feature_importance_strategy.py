# worker/ml/services/strategies/feature_importance_strategy.py
import logging
import pandas as pd
import numpy as np
from typing import Optional, List, Any

try:
    import shap
except ImportError:
    shap = None # Handle optional dependency

from .base_xai_strategy import BaseXAIStrategy
from shared.schemas.xai import FeatureImportanceResultData, FeatureImportanceValue

logger = logging.getLogger(__name__)

class FeatureImportanceStrategy(BaseXAIStrategy):
    """Generates Feature Importance based on mean absolute SHAP values."""

    def explain(self, X_inference: pd.DataFrame, identifiers_df: pd.DataFrame) -> Optional[FeatureImportanceResultData]:
        if shap is None:
            logger.error("SHAP library is not installed. Cannot calculate SHAP-based feature importance.")
            return None
        if X_inference.empty:
            logger.warning("FeatureImportanceStrategy: Input DataFrame is empty.")
            return None

        logger.info(f"Calculating Feature Importance using SHAP for {len(X_inference)} instances...")
        feature_names = X_inference.columns.tolist()

        try:
            # --- Run SHAP ---
            shap_values_pos_class = None
            try:
                # Prioritize TreeExplainer
                explainer = shap.TreeExplainer(self.model)
                shap_values_raw = explainer.shap_values(X_inference)
                shap_values_pos_class = shap_values_raw[:, :, 1]
            except Exception as tree_err:
                logger.warning(f"TreeExplainer failed ({tree_err}). Trying KernelExplainer.")
                background_sample = self.background_data if self.background_data is not None and not self.background_data.empty else X_inference
                if len(background_sample) > 100: background_sample = shap.sample(background_sample, 100)
                if not hasattr(self.model, 'predict_proba'): raise TypeError("KernelExplainer requires predict_proba.")

                explainer = shap.KernelExplainer(self.model.predict_proba, background_sample)
                shap_values_pos_class = explainer.shap_values(X_inference, nsamples='auto')[1]

            if shap_values_pos_class is None:
                 raise RuntimeError("Failed to obtain SHAP values for feature importance.")

            # --- Calculate Mean Absolute SHAP ---
            avg_abs_shap = np.mean(np.abs(shap_values_pos_class), axis=0)

            importance_list: List[FeatureImportanceValue] = [
                FeatureImportanceValue(
                    feature=fn,
                    # Use float() directly which handles numpy floats
                    importance=round(float(imp), 6)
                )
                for fn, imp in zip(feature_names, avg_abs_shap) # avg_abs_shap should be 1D array of shape (n_features,)
            ]

            # Sort by importance descending
            importance_list.sort(key=lambda x: x.importance, reverse=True)

            return FeatureImportanceResultData(feature_importances=importance_list)

        except Exception as e:
            logger.error(f"Error calculating SHAP-based Feature Importance: {e}", exc_info=True)
            return None