# worker/dataset/services/steps/calculate_delta_metrics_step.py
import logging

import numpy as np
import pandas as pd

from services.context import DatasetContext
from services.interfaces import IDatasetGeneratorStep
from shared.db import CK_METRIC_COLUMNS  # Get list of metric columns
from shared.utils.pipeline_logging import StepLogger

logger = logging.getLogger(__name__)


class CalculateDeltaMetricsStep(IDatasetGeneratorStep):
    """Calculates d_* metrics (difference between current and parent CK metrics)."""

    name = "Calculate Delta Metrics"

    def execute(self, context: DatasetContext, **kwargs) -> DatasetContext:
        log_prefix = f"Task {context.task_instance.request.id} - Step [{self.name}]"
        step_logger = StepLogger(logger, log_prefix=log_prefix)

        if context.processed_dataframe is None or context.processed_dataframe.empty:
            step_logger.warning(
                "Input DataFrame is None or empty, skipping delta calculation."
            )
            return context

        delta_df = context.processed_dataframe  # Work directly on the context DataFrame
        step_logger.info(
            f"Calculating delta metrics for DataFrame with shape {delta_df.shape}..."
        )

        # Check if parent metric flag exists, otherwise cannot calculate deltas meaningfully
        if "_parent_metric_found" not in delta_df.columns:
            step_logger.error(
                "'_parent_metric_found' column missing. Cannot calculate delta metrics."
            )
            context.warnings.append(
                f"{self.name}: Missing '_parent_metric_found' column."
            )
            # Add empty delta columns?
            for col in CK_METRIC_COLUMNS:
                delta_df[f"d_{col}"] = np.nan
            context.processed_dataframe = delta_df
            return context

        cols_to_drop = ["_parent_metric_found"]  # Start with the flag column

        try:
            for col in CK_METRIC_COLUMNS:
                current_col = col
                parent_col = f"parent_{col}"
                delta_col = f"d_{col}"

                if current_col in delta_df.columns and parent_col in delta_df.columns:
                    cols_to_drop.append(parent_col)  # Mark parent col for removal later
                    # Convert to numeric, coercing errors to NaN
                    current_numeric = pd.to_numeric(
                        delta_df[current_col], errors="coerce"
                    )
                    parent_numeric = pd.to_numeric(
                        delta_df[parent_col], errors="coerce"
                    )

                    # Calculate delta
                    delta_df[delta_col] = current_numeric - parent_numeric

                    # Set delta to NaN where parent wasn't found or values were non-numeric
                    mask_invalid = (
                        ~delta_df["_parent_metric_found"]
                        | current_numeric.isna()
                        | parent_numeric.isna()
                    )
                    delta_df.loc[mask_invalid, delta_col] = np.nan
                elif current_col not in delta_df.columns:
                    step_logger.warning(
                        f"Current column '{current_col}' not found, cannot calculate delta '{delta_col}'."
                    )
                    delta_df[delta_col] = np.nan  # Add NaN delta column
                elif parent_col not in delta_df.columns:
                    step_logger.warning(
                        f"Parent column '{parent_col}' not found, cannot calculate delta '{delta_col}'."
                    )
                    delta_df[delta_col] = np.nan  # Add NaN delta column

            # Drop parent columns and the flag after calculations
            delta_df.drop(columns=cols_to_drop, inplace=True, errors="ignore")
            context.processed_dataframe = delta_df  # Update context
            step_logger.info("Delta metrics calculation complete.")
        except Exception as e:
            step_logger.error(f"Error calculating delta metrics: {e}", exc_info=True)
            context.warnings.append(f"{self.name}: Error calculating deltas: {e}")

        return context
