# worker/dataset/services/steps/calculate_commit_stats_step.py
import logging
import pandas as pd

from services.interfaces import IDatasetGeneratorStep
from services.context import DatasetContext
from shared.utils.pipeline_logging import StepLogger

logger = logging.getLogger(__name__)

class CalculateCommitStatsStep(IDatasetGeneratorStep):
    """Calculates changed_file_count and lines_per_file for each row."""
    name = "Calculate Commit Stats"

    def execute(self, context: DatasetContext, **kwargs) -> DatasetContext:
        log_prefix = f"Task {context.task_instance.request.id} - Step [{self.name}]"
        step_logger = StepLogger(logger, log_prefix=log_prefix)

        if context.processed_dataframe is None or context.processed_dataframe.empty:
            step_logger.warning("Input DataFrame is None or empty, skipping.")
            return context

        df = context.processed_dataframe
        step_logger.info(f"Calculating commit stats for DataFrame with shape {df.shape}...")

        try:
            if 'files_changed' in df.columns:
                # Ensure we handle non-list entries safely
                df['changed_file_count'] = df['files_changed'].apply(
                    lambda x: len(x) if isinstance(x, list) else 0
                )
            else:
                step_logger.warning("Missing 'files_changed' column, setting 'changed_file_count' to 0.")
                df['changed_file_count'] = 0

            required_line_cols = ['la', 'ld', 'changed_file_count']
            if all(col in df.columns for col in required_line_cols):
                 denominator = df['changed_file_count'].replace(0, 1) # Avoid division by zero
                 df['lines_per_file'] = (df['la'].fillna(0) + df['ld'].fillna(0)) / denominator
            else:
                 missing_cols = [col for col in required_line_cols if col not in df.columns]
                 step_logger.warning(f"Missing columns ({missing_cols}) for 'lines_per_file' calculation, setting to 0.")
                 df['lines_per_file'] = 0

            context.processed_dataframe = df # Update context
            step_logger.info("Commit stats calculation complete.")
        except Exception as e:
            step_logger.error(f"Error calculating commit stats: {e}", exc_info=True)
            context.warnings.append(f"{self.name}: Error calculating stats: {e}")

        return context