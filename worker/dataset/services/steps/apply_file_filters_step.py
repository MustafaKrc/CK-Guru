# worker/dataset/services/steps/apply_file_filters_step.py
import logging
import pandas as pd

from services.interfaces import IDatasetGeneratorStep
from services.context import DatasetContext
from shared.utils.pipeline_logging import StepLogger

logger = logging.getLogger(__name__)

class ApplyFileFiltersStep(IDatasetGeneratorStep):
    """Applies standard file filters (Java, non-test/example/package-info)."""
    name = "Apply File Filters"

    def execute(self, context: DatasetContext, **kwargs) -> DatasetContext:
        log_prefix = f"Task {context.task_instance.request.id} - Step [{self.name}]"
        step_logger = StepLogger(logger, log_prefix=log_prefix)

        if context.processed_dataframe is None or context.processed_dataframe.empty:
            step_logger.warning("Input DataFrame is None or empty, skipping.")
            return context

        df = context.processed_dataframe
        initial_len = len(df)
        step_logger.info(f"Applying file filters to DataFrame with shape {df.shape}...")

        if 'file' not in df.columns:
            step_logger.warning("Missing 'file' column, cannot apply file filters.")
            return context

        try:
            is_java = df['file'].astype(str).str.endswith('.java', na=False)
            is_not_package_info = ~df['file'].astype(str).str.endswith('package-info.java', na=False)
            file_lower = df['file'].astype(str).str.lower()
            is_not_test = ~file_lower.str.contains("test", na=False)
            is_not_example = ~file_lower.str.contains("example", na=False)

            valid_file_mask = is_java & is_not_package_info & is_not_test & is_not_example
            context.processed_dataframe = df[valid_file_mask].copy() # Create copy to avoid SettingWithCopyWarning
            dropped = initial_len - len(context.processed_dataframe)
            step_logger.info(f"File filters dropped {dropped} rows. New shape: {context.processed_dataframe.shape}")
        except Exception as e:
             step_logger.error(f"Error applying file filters: {e}", exc_info=True)
             # Decide: return context as is, or raise error? Let's return for now.
             context.warnings.append(f"{self.name}: Error applying filters: {e}")

        return context