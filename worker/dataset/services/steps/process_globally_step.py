# worker/dataset/services/steps/process_globally_step.py
import logging
import pandas as pd

from services.interfaces import IDatasetGeneratorStep, ICleaningService
# Import sub-steps
from .combine_batches_step import CombineBatchesStep
from .apply_global_cleaning_rules_step import ApplyGlobalCleaningRulesStep

from services.context import DatasetContext
from shared.utils.pipeline_logging import StepLogger

logger = logging.getLogger(__name__)

class ProcessGloballyStep(IDatasetGeneratorStep):
    """Orchestrates global processing: combining batches and applying global rules."""
    name = "Process Globally"

    def __init__(self):
        # Instantiate the sub-steps this orchestrator will run
        self.global_steps = [
            CombineBatchesStep(),
            ApplyGlobalCleaningRulesStep(),
        ]
        logger.debug(f"Initialized with global steps: {[s.name for s in self.global_steps]}")

    def execute(
        self,
        context: DatasetContext,
        *,
        cleaning_service: ICleaningService, # Dependency for sub-step
        **kwargs
    ) -> DatasetContext:
        log_prefix = f"Task {context.task_instance.request.id} - Step [{self.name}]"
        step_logger = StepLogger(logger, log_prefix=log_prefix)
        step_logger.info("Starting global processing...")

        # --- Prepare dependencies for sub-steps ---
        sub_step_deps = {
            "cleaning_service": cleaning_service,
            # Add other deps if needed by global steps
        }

        current_context = context
        try:
            # Execute global sub-steps sequentially
            for sub_step in self.global_steps:
                step_logger.info(f"  Running global sub-step [{sub_step.name}]...")
                current_context = sub_step.execute(current_context, **sub_step_deps)
                # Check if DataFrame became empty after a step
                if current_context.processed_dataframe is None or current_context.processed_dataframe.empty:
                    step_logger.warning(f"DataFrame became empty after global sub-step [{sub_step.name}]. Skipping remaining global steps.")
                    break

            step_logger.info("Global processing complete.")

        except Exception as e:
            step_logger.error(f"Error during global processing: {e}", exc_info=True)
            raise # Re-raise to fail the pipeline

        return current_context # Return the context modified by sub-steps