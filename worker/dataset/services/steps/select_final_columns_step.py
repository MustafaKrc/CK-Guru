# worker/dataset/services/steps/select_final_columns_step.py
import logging

import pandas as pd

from services.context import DatasetContext
from services.interfaces import IDatasetGeneratorStep
from shared.utils.pipeline_logging import StepLogger

logger = logging.getLogger(__name__)


class SelectFinalColumnsStep(IDatasetGeneratorStep):
    """Selects the final feature and target columns for the output dataset."""

    name = "Select Final Columns"

    def execute(self, context: DatasetContext, **kwargs) -> DatasetContext:
        log_prefix = f"Task {context.task_instance.request.id} - Step [{self.name}]"
        step_logger = StepLogger(logger, log_prefix=log_prefix)

        if context.processed_dataframe is None or context.processed_dataframe.empty:
            step_logger.warning(
                "Input DataFrame is None or empty, cannot select final columns."
            )
            context.final_dataframe = (
                pd.DataFrame()
            )  # Ensure final_dataframe is empty df
            return context

        df = context.processed_dataframe
        step_logger.info(
            f"Selecting final columns from DataFrame with shape {df.shape}..."
        )

        if not context.dataset_config:
            step_logger.error(
                "Dataset configuration missing in context. Cannot determine final columns."
            )
            raise ValueError(
                "Dataset configuration required for final column selection."
            )

        feature_columns = context.dataset_config.feature_columns
        target_column = context.dataset_config.target_column

        if not feature_columns:
            step_logger.error("No feature columns defined in dataset configuration.")
            raise ValueError(
                "Feature columns must be specified in dataset configuration."
            )
        if not target_column:
            step_logger.error("No target column defined in dataset configuration.")
            raise ValueError(
                "Target column must be specified in dataset configuration."
            )

        # Check existence
        available_columns = df.columns.tolist()
        missing_features = [c for c in feature_columns if c not in available_columns]
        missing_target = target_column not in available_columns

        if missing_features:
            msg = f"Missing required feature columns: {missing_features}"
            step_logger.error(msg)
            raise ValueError(msg)
        if missing_target:
            msg = f"Missing required target column: {target_column}"
            step_logger.error(msg)
            raise ValueError(msg)

        # Select columns
        final_columns = feature_columns + [target_column]
        try:
            context.final_dataframe = df[final_columns].copy()
            step_logger.info(
                f"Selected {len(final_columns)} final columns. Output shape: {context.final_dataframe.shape}"
            )
        except KeyError as e:
            step_logger.error(
                f"KeyError during final column selection: {e}. Columns: {final_columns}. Available: {available_columns}",
                exc_info=True,
            )
            raise ValueError(f"Failed to select final columns: {e}") from e
        except Exception as e:
            step_logger.error(
                f"Unexpected error during final column selection: {e}", exc_info=True
            )
            raise RuntimeError("Unexpected error selecting final columns") from e

        return context
