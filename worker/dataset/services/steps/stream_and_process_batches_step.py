# worker/dataset/services/steps/stream_and_process_batches_step.py
import logging
from typing import List
import pandas as pd

from services.interfaces import (
    IDatasetGeneratorStep, IDataLoader, ICleaningService, IRepositoryFactory
)
# Import Step classes directly - they are concrete dependencies of this orchestrating step
from .apply_file_filters_step import ApplyFileFiltersStep
from .calculate_commit_stats_step import CalculateCommitStatsStep
from .get_parent_ck_metrics_step import GetParentCKMetricsStep
from .calculate_delta_metrics_step import CalculateDeltaMetricsStep
from .apply_batch_cleaning_rules_step import ApplyBatchCleaningRulesStep
from .drop_missing_parents_step import DropMissingParentsStep

# Import repositories needed by sub-steps
from shared.services.interfaces import IJobStatusUpdater # For progress

from services.context import DatasetContext
from services.data_loader import DataLoader # Import concrete DataLoader for instantiation
from shared.utils.pipeline_logging import StepLogger

logger = logging.getLogger(__name__)

class StreamAndProcessBatchesStep(IDatasetGeneratorStep):
    """Fetches data in batches and applies batch-level processing steps."""
    name = "Stream and Process Batches"

    def __init__(self):
        # Instantiate the sub-steps this orchestrator will run
        self.batch_steps = [
            ApplyFileFiltersStep(),
            CalculateCommitStatsStep(),
            GetParentCKMetricsStep(),
            CalculateDeltaMetricsStep(),
            ApplyBatchCleaningRulesStep(),
            DropMissingParentsStep(),
        ]
        logger.debug(f"Initialized with batch steps: {[s.name for s in self.batch_steps]}")

    def execute(
        self,
        context: DatasetContext,
        *,
        # Dependencies for this step and its sub-steps
        repo_factory: IRepositoryFactory,
        cleaning_service: ICleaningService,
        job_status_updater: IJobStatusUpdater, # For progress within the loop
        session_factory: callable, # Needed for DataLoader
        **kwargs
    ) -> DatasetContext:
        log_prefix = f"Task {context.task_instance.request.id} - Step [{self.name}]"
        step_logger = StepLogger(logger, log_prefix=log_prefix)

        if not context.repository_db or not context.dataset_config:
            raise ValueError("Repository DB object or Dataset Config missing in context.")

        # --- Initialize DataLoader ---
        # Pass session_factory to DataLoader
        data_loader: IDataLoader = DataLoader(
            session_factory=session_factory,
            repository_id=context.repository_db.id,
            bot_patterns=context.bot_patterns_db
        )

        # --- Prepare dependencies for sub-steps ---
        # Get repositories needed by sub-steps ONCE
        ck_metric_repo = repo_factory.get_ck_metric_repo()
        sub_step_deps = {
            "cleaning_service": cleaning_service,
            "ck_repo": ck_metric_repo,
            # Add other repos/services if sub-steps need them
        }

        # --- Batch Processing Loop ---
        step_logger.info("Starting data batch streaming and processing...")
        batch_size = 1000 # TODO: Make configurable?
        context.estimated_total_rows = data_loader.estimate_total_rows()
        processed_batches_list: List[pd.DataFrame] = []
        processed_row_count = 0
        batch_num = 0

        try:
            for batch_df in data_loader.stream_batches(batch_size):
                batch_num += 1
                rows_in_batch = len(batch_df)
                step_logger.debug(f"Processing Batch {batch_num} ({rows_in_batch} rows)...")

                # Create a temporary context for this batch's processing
                batch_context = DatasetContext(
                    dataset_id=context.dataset_id,
                    dataset_config=context.dataset_config,
                    task_instance=context.task_instance, # Pass task for potential logging in sub-steps
                    processed_dataframe=batch_df # Start with the loaded batch
                )

                # Execute batch sub-steps sequentially
                for sub_step in self.batch_steps:
                    if batch_context.processed_dataframe is None or batch_context.processed_dataframe.empty:
                        step_logger.debug(f"Batch {batch_num} became empty after step [{sub_step.name}]. Skipping remaining batch steps.")
                        break
                    step_logger.debug(f"  Batch {batch_num}: Running sub-step [{sub_step.name}]...")
                    try:
                        batch_context = sub_step.execute(batch_context, **sub_step_deps)
                    except Exception as sub_step_err:
                        # Log error but try to continue with next batch? Or fail hard?
                        # Let's fail hard for now if a sub-step fails.
                        step_logger.error(f"Error in sub-step [{sub_step.name}] for batch {batch_num}: {sub_step_err}", exc_info=True)
                        raise RuntimeError(f"Sub-step [{sub_step.name}] failed") from sub_step_err

                # Add the final processed batch df to our list if not empty
                if batch_context.processed_dataframe is not None and not batch_context.processed_dataframe.empty:
                    processed_batches_list.append(batch_context.processed_dataframe)
                    processed_row_count += len(batch_context.processed_dataframe)

                # Update overall progress
                # Calculate progress based on estimated rows processed (input count)
                # Note: processed_row_count here reflects rows *after* filtering in the batch
                estimated_rows_processed_so_far = batch_num * batch_size
                progress = 5 + int(45 * min(1.0, estimated_rows_processed_so_far / context.estimated_total_rows))
                # Use job_status_updater for DB update consistency
                job_status_updater.update_dataset_progress(
                    context.dataset_id,
                    message=f"Processing batch {batch_num}..."
                )
                # Update Celery task state
                context.task_instance.update_state(state='PROGRESS', meta={'progress': progress, 'step': f"Processing Batch {batch_num}"})


            # Store the list of processed batches in the main context
            context.processed_batches_data = processed_batches_list
            step_logger.info(f"Finished processing {batch_num} batches. Total rows after batch processing: {processed_row_count}")

        except Exception as e:
            step_logger.error(f"Error during batch streaming/processing loop: {e}", exc_info=True)
            raise # Re-raise to fail the pipeline

        return context