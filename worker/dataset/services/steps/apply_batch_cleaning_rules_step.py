# worker/dataset/services/steps/apply_batch_cleaning_rules_step.py
import logging

from services.context import DatasetContext
from services.interfaces import ICleaningService, IDatasetGeneratorStep
from shared.utils.pipeline_logging import StepLogger

logger = logging.getLogger(__name__)


class ApplyBatchCleaningRulesStep(IDatasetGeneratorStep):
    """Applies configured batch-safe cleaning rules using the Cleaning Service."""

    name = "Apply Batch Cleaning Rules"

    def execute(
        self, context: DatasetContext, *, cleaning_service: ICleaningService, **kwargs
    ) -> DatasetContext:
        log_prefix = f"Task {context.task_instance.request.id} - Step [{self.name}]"
        step_logger = StepLogger(logger, log_prefix=log_prefix)

        if context.processed_dataframe is None or context.processed_dataframe.empty:
            step_logger.warning(
                "Input DataFrame is None or empty, skipping batch cleaning."
            )
            return context

        df = context.processed_dataframe
        initial_shape = df.shape
        step_logger.info(
            f"Applying batch cleaning rules to DataFrame with shape {initial_shape}..."
        )

        try:
            context.processed_dataframe = cleaning_service.apply_batch_rules(df)
            final_shape = context.processed_dataframe.shape
            step_logger.info(
                f"Batch cleaning rules applied. Shape change: {initial_shape} -> {final_shape}"
            )
            if context.processed_dataframe.empty:
                step_logger.warning(
                    "DataFrame is empty after applying batch cleaning rules."
                )
                context.warnings.append(f"{self.name}: DataFrame became empty.")
        except Exception as e:
            step_logger.error(
                f"Error applying batch cleaning rules: {e}", exc_info=True
            )
            context.warnings.append(f"{self.name}: Error during batch cleaning: {e}")
            # Decide: return original df or raise? Let's return context as is.

        return context
