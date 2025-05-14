# worker/ml/services/strategies/feature_importance_strategy.py
import logging
from typing import Any, List, Optional  # Added Any

import numpy as np
import pandas as pd
import shap  # SHAP is a fallback, so still attempt import

from shared.core.config import settings
from shared.schemas.xai import FeatureImportanceResultData, FeatureImportanceValue

from .base_xai_strategy import BaseXAIStrategy

# Need SHAPStrategy if we are calling it internally
from .shap_strategy import SHAPStrategy

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


class FeatureImportanceStrategy(BaseXAIStrategy):
    """
    Generates Feature Importance.
    Attempts to use native model attributes (feature_importances_ or coef_) first.
    If not available or applicable, falls back to mean absolute SHAP values.
    """

    def __init__(self, model: Any, background_data: Optional[pd.DataFrame] = None):
        super().__init__(model, background_data)
        # self.shap_strategy_instance: Optional[SHAPStrategy] = None # To lazy-load if needed

    def _get_native_importances(
        self, feature_names: List[str]
    ) -> Optional[List[FeatureImportanceValue]]:
        """Attempts to get feature importances from native model attributes."""
        importances_array: Optional[np.ndarray] = None
        source = "unknown"

        if hasattr(self.model, "feature_importances_"):
            try:
                importances_array = self.model.feature_importances_
                source = "feature_importances_"
                logger.info(
                    f"Found native '{source}' attribute for feature importance."
                )
            except Exception as e:
                logger.warning(f"Error accessing 'feature_importances_': {e}")
                importances_array = None

        if importances_array is None and hasattr(self.model, "coef_"):
            try:
                # For linear models, coef_ can be (n_classes-1, n_features) or (n_features,) for binary after squeeze
                # or (n_classes, n_features) for multi-class one-vs-rest.
                # We are interested in the magnitude for importance.
                coeffs = self.model.coef_
                if (
                    coeffs.ndim == 2
                ):  # e.g., (1, n_features) for binary or (n_classes, n_features)
                    if (
                        coeffs.shape[0] == 1
                    ):  # Binary case, already effectively for the positive class
                        importances_array = np.abs(coeffs[0])
                    else:  # Multi-class, average abs importance across classes or pick one?
                        # For simplicity, let's average absolute coefficients across classes.
                        logger.warning(
                            "Multi-class coefficients found. Averaging absolute values for importance."
                        )
                        importances_array = np.mean(np.abs(coeffs), axis=0)
                elif coeffs.ndim == 1:  # Directly n_features
                    importances_array = np.abs(coeffs)
                else:
                    logger.warning(
                        f"Model 'coef_' has unexpected shape {coeffs.shape}. Cannot directly use for importance."
                    )

                if importances_array is not None:
                    source = "coef_"
                    logger.info(
                        f"Found native '{source}' attribute for feature importance."
                    )

            except Exception as e:
                logger.warning(f"Error accessing 'coef_': {e}")
                importances_array = None

        if importances_array is not None:
            if len(importances_array) == len(feature_names):
                importance_list: List[FeatureImportanceValue] = [
                    FeatureImportanceValue(
                        feature=fn,
                        importance=round(float(imp), 6),
                    )
                    for fn, imp in zip(feature_names, importances_array)
                ]
                importance_list.sort(key=lambda x: x.importance, reverse=True)
                logger.info(
                    f"Successfully extracted native feature importances from '{source}'."
                )
                return importance_list
            else:
                logger.error(
                    f"Native feature importance array length ({len(importances_array)}) "
                    f"mismatches feature names length ({len(feature_names)}). Source: {source}."
                )
        return None

    def _get_shap_based_importances(
        self,
        X_inference: pd.DataFrame,
        identifiers_df: pd.DataFrame,
        feature_names: List[str],
    ) -> Optional[List[FeatureImportanceValue]]:
        """Calculates feature importances using SHAP values as a fallback."""
        if shap is None:
            logger.error(
                "SHAP library not installed. Cannot calculate SHAP-based feature importance."
            )
            return None

        logger.info("Calculating SHAP-based feature importances as fallback...")
        try:
            # Instantiate SHAPStrategy on demand
            # if self.shap_strategy_instance is None:
            #     self.shap_strategy_instance = SHAPStrategy(self.model, self.background_data)

            # For encapsulation, let's create a temporary SHAPStrategy instance here.
            # This ensures FeatureImportanceStrategy doesn't permanently hold a SHAPStrategy.
            temp_shap_strategy = SHAPStrategy(self.model, self.background_data)

            shap_result_data_container = temp_shap_strategy.explain(
                X_inference, identifiers_df
            )

            if (
                shap_result_data_container
                and shap_result_data_container.instance_shap_values
            ):
                all_shap_values_for_positive_class = []
                for (
                    instance_shap_result
                ) in shap_result_data_container.instance_shap_values:
                    # Each `instance_shap_result.shap_values` is a List[FeatureSHAPValue]
                    # We need the .value attribute from each FeatureSHAPValue object
                    instance_s_values = [
                        fsv.value for fsv in instance_shap_result.shap_values
                    ]
                    if len(instance_s_values) == len(
                        feature_names
                    ):  # Ensure correct number of features
                        all_shap_values_for_positive_class.append(instance_s_values)
                    else:
                        logger.warning(
                            f"SHAP values length mismatch for an instance. Expected {len(feature_names)}, got {len(instance_s_values)}"
                        )

                if not all_shap_values_for_positive_class:
                    logger.error(
                        "SHAP-based importance: No valid SHAP values collected from instances."
                    )
                    return None

                # Calculate mean absolute SHAP values across all instances
                mean_abs_shap = np.mean(
                    np.abs(np.array(all_shap_values_for_positive_class)), axis=0
                )

                if len(mean_abs_shap) != len(feature_names):
                    logger.error(
                        f"Mean absolute SHAP array length ({len(mean_abs_shap)}) mismatch with feature names ({len(feature_names)})."
                    )
                    return None

                importance_list: List[FeatureImportanceValue] = [
                    FeatureImportanceValue(
                        feature=fn,
                        importance=round(float(imp), 6),
                    )
                    for fn, imp in zip(feature_names, mean_abs_shap)
                ]
                importance_list.sort(key=lambda x: x.importance, reverse=True)
                logger.info("Successfully calculated SHAP-based feature importances.")
                return importance_list
            else:
                logger.error(
                    "SHAP-based importance calculation failed or returned no instance SHAP values from SHAPStrategy."
                )
                return None
        except Exception as shap_e:
            logger.error(
                f"Error during SHAP-based fallback for feature importance: {shap_e}",
                exc_info=True,
            )
            return None

    def explain(
        self, X_inference: pd.DataFrame, identifiers_df: pd.DataFrame
    ) -> Optional[FeatureImportanceResultData]:
        if X_inference.empty:
            logger.warning(
                "FeatureImportanceStrategy: Input DataFrame X_inference is empty."
            )
            return None

        feature_names = X_inference.columns.tolist()
        if not feature_names:
            logger.error(
                "FeatureImportanceStrategy: No feature names found in X_inference."
            )
            return None

        logger.info(
            f"Generating Feature Importance for {len(X_inference)} instances..."
        )

        # 1. Attempt to get native importances
        importance_list = self._get_native_importances(feature_names)

        # 2. If native not found, fall back to SHAP-based
        if importance_list is None:
            logger.info(
                "Native feature importances not found or applicable. Attempting SHAP-based calculation."
            )
            importance_list = self._get_shap_based_importances(
                X_inference, identifiers_df, feature_names
            )

        if importance_list is not None:
            return FeatureImportanceResultData(feature_importances=importance_list)
        else:
            logger.error(
                "Failed to generate feature importances using both native and SHAP-based methods."
            )
            return None
