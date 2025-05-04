# worker/dataset/services/steps/apply_global_cleaning_rules_step.py
import logging
import pandas as pd

from services.interfaces import IDatasetGeneratorStep, ICleaningService
from services.context import DatasetContext
from shared.utils.pipeline_logging import StepLogger

logger = logging.getLogger(__name__)

class ApplyGlobalCleaningRulesStep(IDatasetGeneratorStep):
    """Applies configured global cleaning rules using the Cleaning Service."""
    name = "Apply Global Cleaning Rules"

    def execute(self, context: DatasetContext, *, cleaning_service: ICleaningService, **kwargs) -> DatasetContext:
        log_prefix = f"Task {context.task_instance.request.id} - Step [{self.name}]"
        step_logger = StepLogger(logger, log_prefix=log_prefix)

        if context.processed_dataframe is None or context.processed_dataframe.empty:
            step_logger.warning("Input DataFrame is None or empty, skipping global cleaning.")
            return context

        df = context.processed_dataframe
        initial_shape = df.shape
        step_logger.info(f"Applying global cleaning rules to DataFrame with shape {initial_shape}...")

        try:
            context.processed_dataframe = cleaning_service.apply_global_rules(df)
            final_shape = context.processed_dataframe.shape
            step_logger.info(f"Global cleaning rules applied. Shape change: {initial_shape} -> {final_shape}")
            if context.processed_dataframe.empty:
                 step_logger.warning("DataFrame is empty after applying global cleaning rules.")
                 context.warnings.append(f"{self.name}: DataFrame became empty.")
        except Exception as e:
            step_logger.error(f"Error applying global cleaning rules: {e}", exc_info=True)
            context.warnings.append(f"{self.name}: Error during global cleaning: {e}")
            # Decide: return original df or raise? Let's return context as is.

        return context