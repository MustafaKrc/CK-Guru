# worker/dataset/services/steps/combine_batches_step.py
import logging

import pandas as pd
from services.context import DatasetContext
from services.interfaces import IDatasetGeneratorStep

from shared.utils.pipeline_logging import StepLogger

logger = logging.getLogger(__name__)


class CombineBatchesStep(IDatasetGeneratorStep):
    """Combines processed data batches into a single DataFrame."""

    name = "Combine Batches"

    def execute(self, context: DatasetContext, **kwargs) -> DatasetContext:
        log_prefix = f"Task {context.task_instance.request.id} - Step [{self.name}]"
        step_logger = StepLogger(logger, log_prefix=log_prefix)

        if not context.processed_batches_data:
            step_logger.warning(
                "No processed batch data found in context. Setting processed_dataframe to empty."
            )
            context.processed_dataframe = pd.DataFrame()
            return context

        num_batches = len(context.processed_batches_data)
        step_logger.info(f"Combining {num_batches} processed data batches...")

        try:
            # Concatenate list of DataFrames
            context.processed_dataframe = pd.concat(
                context.processed_batches_data, ignore_index=True, sort=False
            )
            # Clear the batch data list from context to free memory
            context.processed_batches_data = None
            step_logger.info(
                f"Combined DataFrame shape: {context.processed_dataframe.shape}"
            )
        except Exception as e:
            step_logger.error(f"Error combining batches: {e}", exc_info=True)
            context.warnings.append(f"{self.name}: Error combining batches: {e}")
            # Set to empty DataFrame on error?
            context.processed_dataframe = pd.DataFrame()
            raise RuntimeError("Failed to combine processed batches") from e

        return context
