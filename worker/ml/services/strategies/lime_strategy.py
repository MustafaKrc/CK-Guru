# worker/ml/services/strategies/lime_strategy.py
import logging
from typing import List, Optional, Tuple

import pandas as pd

try:
    import lime
    import lime.lime_tabular
except ImportError:
    lime = None  # Handle optional dependency

from shared.schemas.xai import InstanceLIMEResult, LIMEResultData

from .base_xai_strategy import BaseXAIStrategy

logger = logging.getLogger(__name__)


class LIMEStrategy(BaseXAIStrategy):
    """Generates LIME explanations."""

    def explain(
        self, X_inference: pd.DataFrame, identifiers_df: pd.DataFrame
    ) -> Optional[LIMEResultData]:
        if lime is None:
            logger.error(
                "LIME library is not installed. Cannot generate LIME explanations."
            )
            return None
        if X_inference.empty:
            logger.warning(
                "LIMEStrategy: Input DataFrame is empty. No explanations generated."
            )
            return None
        if self.background_data is None or self.background_data.empty:
            logger.error(
                "LIMEStrategy: Background data is required but missing or empty."
            )
            # Or potentially fallback to using X_inference as background, but log heavily
            # return None
            logger.warning(
                "Using inference data as background data for LIME (less ideal)."
            )
            self.background_data = X_inference  # Fallback - use with caution

        # Ensure model has predict_proba
        if not hasattr(self.model, "predict_proba"):
            logger.error("LIMEStrategy: Model requires a 'predict_proba' method.")
            return None

        logger.info(f"Generating LIME explanations for {len(X_inference)} instances...")
        feature_names = X_inference.columns.tolist()
        class_names = ["clean", "defect-prone"]  # Assuming binary classification

        try:
            # Create LIME explainer
            # Consider checking dtypes: LIME often works best with numerical data,
            # categorical features might need specific handling (e.g., one-hot encoding before LIME)
            # or specific parameters passed to LimeTabularExplainer.
            explainer = lime.lime_tabular.LimeTabularExplainer(
                training_data=self.background_data.values,  # Use numpy array
                feature_names=feature_names,
                class_names=class_names,
                mode="classification",
                random_state=42,  # For reproducibility
            )

            instance_results: List[InstanceLIMEResult] = []
            num_features_lime = min(
                10, len(feature_names)
            )  # Limit features shown by LIME

            for i in range(len(X_inference)):
                instance_id_row = identifiers_df.iloc[i]
                instance_features = X_inference.iloc[i].values

                try:
                    # Explain instance for the positive class (index 1)
                    explanation = explainer.explain_instance(
                        data_row=instance_features,
                        predict_fn=self.model.predict_proba,
                        num_features=num_features_lime,
                        labels=(1,),  # Explain only the defect-prone class
                    )
                    # Extract explanation as list of (feature, weight) tuples
                    lime_explanation: List[Tuple[str, float]] = [
                        (f, round(float(w), 4)) for f, w in explanation.as_list(label=1)
                    ]

                    instance_results.append(
                        InstanceLIMEResult(
                            file=instance_id_row.get("file"),
                            class_name=instance_id_row.get("class_name"),
                            explanation=lime_explanation,
                        )
                    )
                except Exception as instance_err:
                    logger.error(
                        f"LIME explanation failed for instance index {i}: {instance_err}",
                        exc_info=True,
                    )
                    # Optionally append a placeholder or skip the instance

            if not instance_results:
                logger.warning("LIME explanation generated no valid instance results.")
                return None

            return LIMEResultData(instance_lime_values=instance_results)

        except Exception as e:
            logger.error(f"Error generating LIME explanation: {e}", exc_info=True)
            return None
