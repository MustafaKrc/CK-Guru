# worker/ml/services/strategies/shap_strategy.py
import logging
from typing import Any, List, Optional

import numpy as np
import pandas as pd
import shap

from shared.schemas.xai import FeatureSHAPValue, InstanceSHAPResult, SHAPResultData

from .base_xai_strategy import BaseXAIStrategy

logger = logging.getLogger(__name__)


class SHAPStrategy(BaseXAIStrategy):
    def explain(
        self, X_inference: pd.DataFrame, identifiers_df: pd.DataFrame
    ) -> Optional[SHAPResultData]:
        if X_inference.empty:
            logger.warning(
                "SHAPStrategy: Input DataFrame is empty. No explanations generated."
            )
            return None

        logger.info(f"Generating SHAP explanations for {len(X_inference)} instances...")
        feature_names = X_inference.columns.tolist()

        try:
            explainer_type_used = "Unknown"
            shap_values_pos_class: Optional[np.ndarray] = None
            explainer_expected_value: Optional[Any] = None

            try:
                explainer = shap.TreeExplainer(
                    self.model,
                    self.background_data,
                    feature_perturbation="tree_path_dependent",
                )
                explainer_type_used = "TreeExplainer"
                explainer_expected_value = explainer.expected_value

                shap_values_raw = explainer.shap_values(X_inference)

                if isinstance(shap_values_raw, list) and len(shap_values_raw) == 2:
                    shap_values_pos_class = shap_values_raw[1]
                    logger.info(
                        f"SHAPStrategy ({explainer_type_used}): Extracted SHAP values for positive class from list output. Shape: {shap_values_pos_class.shape if shap_values_pos_class is not None else 'None'}"
                    )
                elif (
                    isinstance(shap_values_raw, np.ndarray)
                    and shap_values_raw.ndim == 2
                    and shap_values_raw.shape == X_inference.shape
                ):
                    shap_values_pos_class = shap_values_raw
                    logger.info(
                        f"SHAPStrategy ({explainer_type_used}): Used 2D SHAP values array directly. Shape: {shap_values_pos_class.shape}"
                    )
                else:
                    logger.warning(
                        f"SHAPStrategy ({explainer_type_used}): Unexpected SHAP values structure. Type: {type(shap_values_raw)}, Shape: {getattr(shap_values_raw, 'shape', 'N/A')}."
                    )
                    raise ValueError(
                        f"Unexpected SHAP values structure from {explainer_type_used}."
                    )

            except Exception as tree_explainer_err:
                logger.warning(
                    f"SHAPStrategy: {explainer_type_used} failed ('{tree_explainer_err}'). Trying KernelExplainer (slower)."
                )
                explainer_type_used = "KernelExplainer"

                current_background_data = self.background_data
                if current_background_data is None or current_background_data.empty:
                    logger.warning(
                        "SHAPStrategy: KernelExplainer needs background data. Sampling from inference data."
                    )
                    current_background_data = shap.sample(
                        X_inference, min(100, X_inference.shape[0])
                    )
                elif len(current_background_data) > 100:
                    current_background_data = shap.sample(current_background_data, 100)

                if not hasattr(self.model, "predict_proba"):
                    logger.error(
                        f"Model {type(self.model).__name__} needs predict_proba for KernelExplainer."
                    )
                    return None

                def predict_proba_wrapper(X_np_array):
                    X_df_wrapped = pd.DataFrame(X_np_array, columns=feature_names)
                    return self.model.predict_proba(X_df_wrapped)

                explainer = shap.KernelExplainer(
                    predict_proba_wrapper, current_background_data
                )
                explainer_expected_value = explainer.expected_value

                shap_values_raw_kernel = explainer.shap_values(
                    X_inference, nsamples="auto", l1_reg="auto"
                )

                if (
                    isinstance(shap_values_raw_kernel, list)
                    and len(shap_values_raw_kernel) == 2
                ):
                    shap_values_pos_class = shap_values_raw_kernel[1]
                    logger.info(
                        f"SHAPStrategy ({explainer_type_used}): Extracted SHAP values for positive class (P(1|x)) from list output. Shape: {shap_values_pos_class.shape if shap_values_pos_class is not None else 'None'}"
                    )
                elif (
                    isinstance(shap_values_raw_kernel, np.ndarray)
                    and shap_values_raw_kernel.ndim == 3
                    and shap_values_raw_kernel.shape[0] == X_inference.shape[0]
                    and shap_values_raw_kernel.shape[1] == X_inference.shape[1]
                    and shap_values_raw_kernel.shape[2] == 2
                ):
                    shap_values_pos_class = shap_values_raw_kernel[:, :, 1]
                    logger.info(
                        f"SHAPStrategy ({explainer_type_used}): Extracted SHAP values for positive class from 3D array output. Shape: {shap_values_pos_class.shape if shap_values_pos_class is not None else 'None'}"
                    )
                else:
                    logger.error(
                        f"SHAPStrategy ({explainer_type_used}): Unexpected SHAP values structure. Type: {type(shap_values_raw_kernel)}, Shape: {getattr(shap_values_raw_kernel, 'shape', 'N/A')}"
                    )
                    return None

            if shap_values_pos_class is None:
                logger.error(
                    f"SHAPStrategy ({explainer_type_used}): Failed to obtain SHAP values for the positive class."
                )
                return None
            if (
                shap_values_pos_class.shape[0] != X_inference.shape[0]
                or shap_values_pos_class.shape[1] != X_inference.shape[1]
            ):
                logger.error(
                    f"SHAPStrategy ({explainer_type_used}): Shape mismatch. SHAP values shape {shap_values_pos_class.shape}, X_inference shape {X_inference.shape}"
                )
                return None

            instance_results: List[InstanceSHAPResult] = []
            for i in range(len(identifiers_df)):
                instance_id_row = identifiers_df.iloc[i]
                shap_values_for_instance = shap_values_pos_class[i]

                if len(shap_values_for_instance) != len(feature_names):
                    logger.error(
                        f"SHAP value count mismatch for instance {i} (Explainer: {explainer_type_used}). Expected {len(feature_names)}, got {len(shap_values_for_instance)}. Skipping instance."
                    )
                    continue

                instance_list: List[FeatureSHAPValue] = []
                for idx, (fn, sv) in enumerate(
                    zip(feature_names, shap_values_for_instance)
                ):
                    # --- Convert numpy types to Python native types ---
                    original_feature_value = X_inference.iloc[i, idx]
                    if isinstance(
                        original_feature_value, np.generic
                    ):  # Covers np.int64, np.float64, etc.
                        py_feature_value = original_feature_value.item()
                    else:
                        py_feature_value = original_feature_value

                    shap_value_float = float(
                        sv
                    )  # SHAP values are usually float already

                    instance_list.append(
                        FeatureSHAPValue(
                            feature=fn,
                            value=round(shap_value_float, 4),  # Use converted float
                            feature_value=py_feature_value,  # Use converted Python native type
                        )
                    )

                base_value_float: Optional[float] = None
                if explainer_expected_value is not None:
                    # Convert explainer_expected_value to float, handling different structures
                    if isinstance(explainer_expected_value, (list, np.ndarray)):
                        target_ev_value = None
                        if len(explainer_expected_value) == 2:
                            target_ev_value = explainer_expected_value[1]
                        elif len(explainer_expected_value) == 1:
                            target_ev_value = explainer_expected_value[0]
                        elif (
                            explainer_type_used == "TreeExplainer"
                            and isinstance(explainer_expected_value, np.ndarray)
                            and explainer_expected_value.ndim == 2
                            and explainer_expected_value.shape[0]
                            == X_inference.shape[0]
                            and explainer_expected_value.shape[1] == 2
                        ):  # (n_samples, n_outputs) from some TreeExplainers
                            target_ev_value = explainer_expected_value[i, 1]
                        elif (
                            explainer_type_used == "TreeExplainer"
                            and isinstance(explainer_expected_value, np.ndarray)
                            and explainer_expected_value.ndim == 1
                            and len(explainer_expected_value) == X_inference.shape[0]
                        ):  # (n_samples,)
                            target_ev_value = explainer_expected_value[i]

                        if target_ev_value is not None:
                            base_value_float = float(
                                target_ev_value
                            )  # Ensure it's Python float
                        else:
                            logger.warning(
                                f"SHAPStrategy: Could not determine specific expected_value for positive class from structure: {explainer_expected_value}"
                            )
                    elif isinstance(
                        explainer_expected_value, (float, np.float_, int, np.integer)
                    ):  # Added np.integer
                        base_value_float = float(
                            explainer_expected_value
                        )  # Ensure it's Python float
                    else:
                        logger.warning(
                            f"SHAPStrategy: explainer.expected_value type ({type(explainer_expected_value)}) for {explainer_type_used} not directly convertible to single float. Value: {explainer_expected_value}"
                        )

                instance_results.append(
                    InstanceSHAPResult(
                        file=instance_id_row.get("file"),
                        class_name=instance_id_row.get("class_name"),
                        shap_values=instance_list,
                        base_value=(
                            round(base_value_float, 4)
                            if base_value_float is not None
                            else None
                        ),
                    )
                )

            if not instance_results:
                logger.warning(
                    f"SHAP explanation ({explainer_type_used}) generated no valid instance results."
                )
                return None

            return SHAPResultData(instance_shap_values=instance_results)

        except Exception as e:
            logger.error(f"Error generating SHAP explanation: {e}", exc_info=True)
            return None
