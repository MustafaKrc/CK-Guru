# worker/dataset/services/steps/drop_missing_parents_step.py
import logging

from services.context import DatasetContext
from services.interfaces import IDatasetGeneratorStep
from shared.utils.pipeline_logging import StepLogger

logger = logging.getLogger(__name__)


class DropMissingParentsStep(IDatasetGeneratorStep):
    """Drops rows where the parent CK metric could not be found."""

    name = "Drop Missing Parents"

    def execute(self, context: DatasetContext, **kwargs) -> DatasetContext:
        log_prefix = f"Task {context.task_instance.request.id} - Step [{self.name}]"
        step_logger = StepLogger(logger, log_prefix=log_prefix)

        if context.processed_dataframe is None or context.processed_dataframe.empty:
            step_logger.warning("Input DataFrame is None or empty, skipping.")
            return context

        df = context.processed_dataframe

        # This step relies on the flag column added by GetParentCKMetricsStep
        # and NOT removed by CalculateDeltaMetricsStep yet.
        # Let's adjust CalculateDeltaMetricsStep to remove it *after* this step.
        if "_parent_metric_found" not in df.columns:
            step_logger.warning(
                "'_parent_metric_found' column not present. Assuming no parents were missing or step was skipped."
            )
            return context  # Return context unmodified if flag isn't there

        initial_rows = len(df)
        step_logger.info(
            f"Dropping rows with missing parents from DataFrame with shape {df.shape}..."
        )

        try:
            # Keep rows WHERE parent WAS found (flag is True)
            context.processed_dataframe = df[df["_parent_metric_found"] == True].copy()
            # Now drop the flag column as it's served its purpose
            context.processed_dataframe.drop(
                columns=["_parent_metric_found"], inplace=True, errors="ignore"
            )

            dropped = initial_rows - len(context.processed_dataframe)
            step_logger.info(
                f"Dropped {dropped} rows due to missing parent metrics. New shape: {context.processed_dataframe.shape}"
            )
        except Exception as e:
            step_logger.error(
                f"Error dropping rows with missing parents: {e}", exc_info=True
            )
            context.warnings.append(f"{self.name}: Error dropping rows: {e}")
            # Return original DataFrame if error occurs? Or filtered one? Let's return context as is.
            # Revert df in context?
            context.processed_dataframe = df  # Revert to df before filtering attempt

        return context
