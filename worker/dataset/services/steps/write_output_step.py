# worker/dataset/services/steps/write_output_step.py
import logging

from services.context import DatasetContext

# Import interfaces and concrete services/repositories
from services.interfaces import IDatasetGeneratorStep, IOutputWriter, IRepositoryFactory

from shared.core.config import settings  # For bucket name etc.
from shared.schemas.enums import DatasetStatusEnum
from shared.services.interfaces import IJobStatusUpdater
from shared.utils.pipeline_logging import StepLogger

logger = logging.getLogger(__name__)


class WriteOutputStep(IDatasetGeneratorStep):
    """Selects final columns, writes output Parquet, background sample, and updates final DB status."""

    name = "Write Output"

    def execute(
        self,
        context: DatasetContext,
        *,
        output_writer: IOutputWriter,
        job_status_updater: IJobStatusUpdater,
        repo_factory: IRepositoryFactory,  # Needed to get repo for final update
        **kwargs,
    ) -> DatasetContext:
        log_prefix = f"Task {context.task_instance.request.id} - Step [{self.name}]"
        step_logger = StepLogger(logger, log_prefix=log_prefix)
        step_logger.info("Finalizing and writing output...")

        dataset_repo = repo_factory.get_dataset_repo()  # Get repo for update

        if context.final_dataframe is None or context.final_dataframe.empty:
            msg = "Final DataFrame is empty. Cannot write output."
            step_logger.error(msg)
            # Update DB status to FAILED
            job_status_updater.update_dataset_completion(
                context.dataset_id, DatasetStatusEnum.FAILED, msg
            )
            raise ValueError(msg)  # Fail the pipeline

        df_final = context.final_dataframe
        context.rows_written = len(df_final)
        step_logger.info(f"Preparing to write {context.rows_written} final rows.")

        # --- Define Output URIs ---
        filename = f"dataset_{context.dataset_id}.parquet"
        context.output_storage_uri = (
            f"s3://{settings.S3_BUCKET_NAME}/datasets/{filename}"
        )
        background_filename = f"dataset_{context.dataset_id}_background.parquet"
        context.background_sample_uri = f"s3://{settings.S3_BUCKET_NAME}/datasets/{background_filename}"  # Store potential path

        target_column = (
            context.dataset_config.target_column if context.dataset_config else None
        )

        background_sample_written = False
        try:
            # --- Write Main Dataset ---
            step_logger.info(f"Writing main dataset to {context.output_storage_uri}...")
            # Clear existing before writing
            output_writer.clear_existing(context.output_storage_uri)
            output_writer.write_parquet(
                df_final, context.output_storage_uri, target_column_name=target_column
            )
            step_logger.info("Main dataset written successfully.")

            # --- Write Background Sample ---
            # Configuration (could be moved to context.dataset_config)
            sample_size = 500
            min_rows_for_sampling = 50

            if context.rows_written >= min_rows_for_sampling:
                step_logger.info(
                    f"Creating background data sample (size={sample_size})..."
                )
                background_sample_df = df_final.sample(
                    n=min(sample_size, context.rows_written), random_state=42
                )
                step_logger.info(
                    f"Writing background sample ({background_sample_df.shape}) to {context.background_sample_uri}..."
                )
                output_writer.clear_existing(context.background_sample_uri)
                output_writer.write_parquet(
                    background_sample_df,
                    context.background_sample_uri,
                    target_column_name=target_column,
                )
                background_sample_written = True
                step_logger.info("Background sample written successfully.")
            else:
                step_logger.warning(
                    f"Dataset too small ({context.rows_written} rows) for background sampling (min: {min_rows_for_sampling}). Skipping."
                )
                context.background_sample_uri = (
                    None  # Ensure URI is None if not written
                )

            # --- Final Success Update in DB ---
            final_message = f"Dataset generated ({context.rows_written} rows)."
            if background_sample_written:
                final_message += " Background sample created."
            else:
                final_message += " Background sample skipped."

            updated = job_status_updater.update_dataset_completion(
                context.dataset_id,
                status=DatasetStatusEnum.READY,
                message=final_message,
                storage_path=context.output_storage_uri,
                background_data_path=context.background_sample_uri,  # Pass URI (or None)
            )
            if not updated:
                # This is serious, the file is written but DB state is inconsistent
                step_logger.critical(
                    "Failed to update dataset status to READY in DB after successful write!"
                )
                context.warnings.append(
                    "CRITICAL: Failed to update DB status to READY."
                )
                # Should we raise an error here? The file exists. Let's add warning for now.
            else:
                step_logger.info("Dataset status updated to READY in DB.")

        except Exception as e:
            step_logger.error(
                f"Error during output writing or final DB update: {e}", exc_info=True
            )
            # Attempt to update DB status to FAILED
            fail_msg = f"Failed during output/final update: {e}"
            job_status_updater.update_dataset_completion(
                context.dataset_id, DatasetStatusEnum.FAILED, fail_msg[:1000]
            )
            # Attempt cleanup (best effort)
            if context.output_storage_uri:
                output_writer.clear_existing(context.output_storage_uri)
            if context.background_sample_uri:
                output_writer.clear_existing(context.background_sample_uri)
            raise  # Re-raise the exception to fail the pipeline

        step_logger.info("Output writing and final status update complete.")
        return context  # Return final context
