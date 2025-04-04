# worker/dataset/app/tasks.py
import time
import traceback
from typing import List, Optional

import s3fs
import pandas as pd
import sqlalchemy as sa
from celery import shared_task, Task
from celery.utils.log import get_task_logger
from celery.exceptions import Ignore
from sqlalchemy import Connection, func, select
from sqlalchemy.orm import aliased

from shared.db.models.dataset import Dataset, DatasetStatusEnum
from shared.db.models.ck_metric import CKMetric
from shared.db.models.repository import Repository
from shared.db.models.bot_pattern import BotPattern
from shared.db.models.commit_guru_metric import CommitGuruMetric

# Import shared utils/config
from shared.db_session import get_sync_db_session
from shared.core.config import settings
from shared.cleaning_rules import get_rule_instance
from shared.utils.task_utils import update_task_state

# Import service functions
from services.dataset_steps import (
    CK_METRIC_COLUMNS, 
    COMMIT_GURU_METRIC_COLUMNS, 
    get_bot_filter_condition, 
    calculate_delta_metrics, 
    get_parent_ck_metrics
)


logger = get_task_logger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


@shared_task(bind=True, name='tasks.generate_dataset')
def generate_dataset_task(self: Task, dataset_id: int):
    """
    Generates a dataset file based on the definition stored in the database.
    """
    task_id = self.request.id
    logger.info(f"Task {task_id}: Starting dataset generation for dataset ID: {dataset_id}")
    update_task_state(self, 'STARTED', 'Initializing dataset generation...', 0)

    dataset: Optional[Dataset] = None
    repo: Optional[Repository] = None
    bot_patterns: List[BotPattern] = []
    total_rows_processed = 0
    total_rows_written = 0
    all_batches_data: List[pd.DataFrame] = [] # Accumulator for DataFrames

    try:
        # Use a single synchronous session for the entire task
        with get_sync_db_session() as session: # Use sync session manager

            # 1. Fetch Configuration
            logger.info(f"Task {task_id}: Fetching dataset configuration...")
            dataset = session.get(Dataset, dataset_id) # Use Session.get for PK lookup
            if not dataset:
                raise ValueError(f"Dataset definition with ID {dataset_id} not found.")

            if dataset.status == DatasetStatusEnum.GENERATING:
                 logger.warning(f"Task {task_id}: Dataset {dataset_id} generation already in progress? Proceeding cautiously.")
                 # Or potentially raise an error to prevent concurrent runs

            # Update status to GENERATING
            dataset.status = DatasetStatusEnum.GENERATING
            dataset.status_message = "Fetching configuration and preparing query."
            session.commit()

            # Fetch associated repository and bot patterns
            repo = session.get(Repository, dataset.repository_id)
            if not repo:
                raise ValueError(f"Repository with ID {dataset.repository_id} not found for dataset {dataset_id}.")

            # Fetch relevant bot patterns (repo-specific + global)
            bot_patterns_stmt = select(BotPattern).where(
                (BotPattern.repository_id == repo.id) | (BotPattern.repository_id.is_(None))
            ).order_by(BotPattern.repository_id.nullslast(), BotPattern.id)
            bot_patterns = list(session.execute(bot_patterns_stmt).scalars().all())
            logger.info(f"Task {task_id}: Fetched {len(bot_patterns)} applicable bot patterns.")

            dataset_config = dataset.config if isinstance(dataset.config, dict) else {}
            feature_columns = dataset_config.get('feature_columns', [])
            target_column = dataset_config.get('target_column', 'is_buggy')
            cleaning_rules_config = dataset_config.get('cleaning_rules', [])

            if not feature_columns:
                raise ValueError("Dataset configuration must specify 'feature_columns'.")

            update_task_state(self, 'STARTED', 'Configuration loaded. Querying data...', 5)

            # 2. Construct Base Query
            # Join CommitGuruMetric (aliased as cgm) and CKMetric (aliased as ckm)
            cgm = aliased(CommitGuruMetric, name="cgm") # Alias defined here
            ckm = aliased(CKMetric, name="ckm")

            base_query = (
                select(cgm, ckm)
                .join(ckm, sa.and_(
                    cgm.repository_id == ckm.repository_id,
                    cgm.commit_hash == ckm.commit_hash
                ))
                .where(cgm.repository_id == repo.id)
            )

            # 3. Apply Initial Filters (Bots)
            if bot_patterns:
                # Pass the alias 'cgm' to the filter function
                bot_condition = get_bot_filter_condition(bot_patterns, cgm)
                base_query = base_query.where(sa.not_(bot_condition))

            # 4. Batch Processing with Streaming
            batch_size = 1000 # Adjust batch size based on memory/performance
            logger.info(f"Task {task_id}: Starting data processing in batches of {batch_size}...")

            # --- Define Object Storage Path ---
            dataset_filename = f"dataset_{dataset_id}.parquet"
            # Construct S3 URI
            object_storage_uri = f"s3://{settings.S3_BUCKET_NAME}/datasets/{dataset_filename}"
            logger.info(f"Task {task_id}: Output will be written to: {object_storage_uri}")


            # --- Get Storage Options ---
            storage_options = settings.s3_storage_options

            first_batch = True
            arrow_schema = None

            # Use stream_results for memory efficiency
            conn: Connection = session.connection() # Get underlying DBAPI connection if needed by stream_results? or session.stream()
            stream = session.execute(base_query).yield_per(batch_size) # Use yield_per

            # --- Overwrite existing object at the start ---
            # Important to clear any partial results from previous failed runs
            try:
                logger.warning(f"Task {task_id}: Attempting to overwrite existing object if present: {object_storage_uri}")
                fs = s3fs.S3FileSystem(**storage_options)
                if fs.exists(object_storage_uri):
                    fs.rm(object_storage_uri)
                    logger.info(f"Task {task_id}: Removed existing object at {object_storage_uri}")

            except Exception as overwrite_err:
                # Log error but proceed - maybe bucket doesn't exist yet or permissions issue
                logger.error(f"Task {task_id}: Could not ensure removal of existing object at {object_storage_uri}: {overwrite_err}. Proceeding anyway.")

            est_total_rows = session.execute(select(func.count()).select_from(base_query.subquery())).scalar() or 1

            for i, result_batch in enumerate(stream.partitions(batch_size)):
                num_batches = i + 1
                start_time_batch = time.time()
                if not result_batch: continue

                logger.debug(f"Task {task_id}: Processing batch {i+1}...")
                update_task_state(self, 'STARTED', f'Processing batch {i+1}...', 5 + int(45 * (total_rows_processed / est_total_rows)))

                # Combine results into a DataFrame
                # Extract data correctly based on the select(cgm, ckm) structure
                batch_data = []
                for row in result_batch:
                     cgm_data = {col: getattr(row.cgm, col, None) for col in COMMIT_GURU_METRIC_COLUMNS}
                     ckm_data = {col: getattr(row.ckm, col, None) for col in CK_METRIC_COLUMNS}
                     # Handle potential name collisions if any (none expected with current names)
                     combined_data = {**cgm_data, **ckm_data}
                     combined_data['repository_id'] = repo.id # Add repo_id explicitly if needed later
                     batch_data.append(combined_data)

                if not batch_data: continue
                batch_df = pd.DataFrame(batch_data)
                total_rows_processed += len(batch_df)

                # -- Metric File Filtering --

                logger.debug(f"Task {task_id}: Batch {num_batches} - Applying file filters...")
                initial_batch_len = len(batch_df)

                # Ensure 'file' column exists and handle potential NaNs
                if 'file' not in batch_df.columns:
                    logger.warning(f"Task {task_id}: Batch {num_batches} - 'file' column missing, skipping file filtering.")
                else:
                    # Apply filters using boolean indexing
                    is_java = batch_df['file'].str.endswith('.java', na=False)
                    is_not_package_info = ~batch_df['file'].str.endswith('package-info.java', na=False)
                    # Handle potential non-string types before .lower() and contains()
                    file_lower = batch_df['file'].astype(str).str.lower()
                    is_not_test = ~file_lower.str.contains("test", na=False)
                    is_not_example = ~file_lower.str.contains("example", na=False)

                    valid_file_mask = is_java & is_not_package_info & is_not_test & is_not_example
                    batch_df = batch_df[valid_file_mask]

                    dropped_files = initial_batch_len - len(batch_df)
                    if dropped_files > 0:
                        logger.debug(f"Task {task_id}: Batch {num_batches} - Dropped {dropped_files} rows based on file filters.")

                # Check if batch became empty after filtering
                if batch_df.empty:
                    logger.debug(f"Task {task_id}: Batch {num_batches} - Became empty after file filtering. Skipping rest of batch processing.")
                    continue

                # -- Calculate `changed_file_count` --
                # files_changed is already a list in CommitGuruMetric model if parsed correctly
                batch_df['changed_file_count'] = batch_df['files_changed'].apply(lambda x: len(x) if isinstance(x, list) else 0)
                # Calculate lines_per_file (example - needs refinement)
                batch_df['lines_per_file'] = (batch_df['la'].fillna(0) + batch_df['ld'].fillna(0)) / batch_df['changed_file_count'].replace(0, 1) # Avoid division by zero

                # -- Calculate Delta Metrics --
                logger.debug(f"Task {task_id}: Batch {i+1} - Calculating delta metrics...")
                parent_metrics_df = get_parent_ck_metrics(session, batch_df)
                # Merge parent metrics - use left join to keep all rows from batch_df
                batch_df_merged = batch_df.join(parent_metrics_df)
                batch_df_with_deltas = calculate_delta_metrics(batch_df_merged)

                # -- Apply Configured Cleaning Rules --
                logger.debug(f"Task {task_id}: Batch {i+1} - Applying cleaning rules...")
                cleaned_batch_df = batch_df_with_deltas.copy()
                rules_to_apply = dataset_config.get('cleaning_rules', [])

                for rule_config in rules_to_apply:
                    rule_name = rule_config.get("name")
                    is_enabled = rule_config.get("enabled", False)
                    params = rule_config.get("params", {})

                    if not is_enabled:
                        continue

                    rule_instance = get_rule_instance(rule_name) # Get instance from registry
                    if rule_instance:
                        # Apply rule only if batch safe (or handle differently later)
                        if not rule_instance.is_batch_safe:
                             logger.warning(f"Skipping rule '{rule_name}' in batch mode as it requires global context.")
                             continue
                        try:
                             logger.debug(f"Applying rule: {rule_name}")
                             cleaned_batch_df = rule_instance.apply(cleaned_batch_df, params, dataset_config) # Pass full config
                             logger.debug(f"Rule {rule_name} applied. Shape after: {cleaned_batch_df.shape}")
                        except Exception as e:
                             logger.error(f"Error applying cleaning rule '{rule_name}' in batch {i+1}: {e}", exc_info=True)
                    else:
                         logger.warning(f"Rule '{rule_name}' is enabled in config but no implementation was registered.")


                # -- Filter Rows with Missing Parents --
                # If _parent_metric_found exists and is False, drop the row
                if '_parent_metric_found' in cleaned_batch_df.columns:
                     initial_rows = len(cleaned_batch_df)
                     cleaned_batch_df = cleaned_batch_df[cleaned_batch_df['_parent_metric_found'] != False]
                     dropped = initial_rows - len(cleaned_batch_df)
                     if dropped > 0:
                          logger.debug(f"Dropped {dropped} rows due to missing parent metrics.")

                if not cleaned_batch_df.empty:
                    all_batches_data.append(cleaned_batch_df)

            # --- Global Rule Processing ---
            # If any global rules are defined, apply them to the entire dataset

            if not all_batches_data:
                logger.warning(f"Task {task_id}: No data accumulated after batch processing. Dataset will be empty.")
                full_df = pd.DataFrame() # Create empty dataframe
            else:
                update_task_state(self, 'STARTED', 'Combining batches...', 51)
                logger.info(f"Task {task_id}: Starting global rules processing - Combining {len(all_batches_data)} batches in memory...")
                full_df = pd.concat(all_batches_data, ignore_index=True)
                del all_batches_data # Release memory
                logger.info(f"Task {task_id}: Combined DataFrame shape: {full_df.shape}")

            update_task_state(self, 'STARTED', 'Applying global rules...', 60)
            logger.info(f"Task {task_id}: Applying globally-aware cleaning rules...")

            rules_to_apply = dataset_config.get('cleaning_rules', [])

            for rule_config in rules_to_apply:
                rule_name = rule_config.get("name")
                is_enabled = rule_config.get("enabled", False)
                params = rule_config.get("params", {})

                if not is_enabled:
                    continue

                rule_instance = get_rule_instance(rule_name) # Get instance from registry
                if rule_instance:
                    # Apply global rules
                    if rule_instance and not rule_instance.is_batch_safe:
                        try:
                            logger.debug(f"Applying global rule: {rule_name}")
                            full_df = rule_instance.apply(full_df, params, dataset_config) # Apply to full_df
                            logger.info(f"Global rule '{rule_name}' applied. Shape after: {full_df.shape}")
                        except Exception as e:
                            logger.error(f"Error applying global rule '{rule_name}': {e}", exc_info=True)
                            raise ValueError(f"Error applying global rule '{rule_name}': {e}") from e
                else:
                        logger.warning(f"Rule '{rule_name}' is enabled in config but no implementation was registered.")


            update_task_state(self, 'STARTED', 'Selecting final features...', 90)

            # Final Feature Selection
            final_columns_requested = list(set(feature_columns + ([target_column] if target_column else [])))
            available_final_columns = [col for col in final_columns_requested if col in full_df.columns]

            if not available_final_columns:
                # Check if full_df was empty to begin with
                if full_df.empty:
                    logger.warning("Dataset is empty after all processing, writing empty file.")
                    final_df = pd.DataFrame(columns=final_columns_requested) # Ensure schema consistency if possible
                else:
                    raise ValueError("No requested feature/target columns remain after global processing.")
            else:
                final_df = full_df[available_final_columns].copy()

            update_task_state(self, 'STARTED', 'Writing final dataset...', 95)


            # Write Final Output to S3 (Single Write)
            logger.info(f"Task {task_id}: Writing final dataset ({len(final_df)} rows) to {object_storage_uri}")
            try:
                # Ensure target directory exists (needed by to_parquet with s3fs sometimes)
                # fs.mkdirs(final_s3_path.rsplit('/', 1)[0], exist_ok=True) # Ensure parent exists
                final_df.to_parquet(
                    object_storage_uri,
                    engine='pyarrow',
                    compression='snappy',
                    index=False,
                    storage_options=storage_options
                )
                total_rows_written = len(final_df)
                logger.info(f"Task {task_id}: Successfully wrote final dataset.")
            except Exception as write_err:
                logger.error(f"Task {task_id}: Error writing final dataset to {object_storage_uri}: {write_err}", exc_info=True)
                raise write_err


            logger.info(f"Task {task_id}: Finished processing {total_rows_processed} rows. Written {total_rows_written} rows to {object_storage_uri}.")

            # 5. Update Final Status
            dataset.status = DatasetStatusEnum.READY
            dataset.status_message = f"Dataset generated successfully. {total_rows_written} rows written."
            dataset.storage_path = object_storage_uri
            session.commit()
            update_task_state(self, 'SUCCESS', dataset.status_message, 100)
            logger.info(f"Task {task_id}: Dataset {dataset_id} marked as READY.")
            return {'dataset_id': dataset_id, 'status': 'SUCCESS', 'rows_written': total_rows_written, 'path': dataset.storage_path}

    except Exception as e:
        # Log detailed error
        error_msg = f"Dataset generation failed for ID {dataset_id}: {type(e).__name__} - {e}"
        logger.error(f"Task {task_id}: {error_msg}", exc_info=True)
        detailed_error = f"{error_msg}\n{traceback.format_exc()}"
        update_task_state(self, 'FAILURE', error_msg, 0)

        # Attempt to update DB status to FAILED
        try:
            # Need a new session if the previous one failed/rolled back
            with get_sync_db_session() as error_session:
                error_dataset = error_session.get(Dataset, dataset_id)
                if error_dataset:
                    error_dataset.status = DatasetStatusEnum.FAILED
                    # Truncate error message if too long for DB field
                    error_dataset.status_message = detailed_error[:1000] # Limit message length
                    error_session.commit()
        except Exception as db_update_err:
            logger.error(f"Task {task_id}: CRITICAL - Failed to update dataset status to FAILED in DB: {db_update_err}")


        # Clean up potentially partially written OBJECT in storage
        if object_storage_uri:
            try:
                logger.warning(f"Task {task_id}: Attempting to delete potentially incomplete object: {object_storage_uri}")
                fs = s3fs.S3FileSystem(**settings.s3_storage_options) # Get fs instance again
                if fs.exists(object_storage_uri):
                    fs.rm(object_storage_uri)
                    logger.info(f"Task {task_id}: Deleted incomplete object: {object_storage_uri}")
            except Exception as cleanup_err:
                logger.error(f"Task {task_id}: Failed to delete incomplete object {object_storage_uri} after error: {cleanup_err}")

        # Re-raise the exception so Celery marks the task as failed
        raise e

@shared_task(
    bind=True,
    name='tasks.delete_storage_object',
    autoretry_for=(ConnectionError, TimeoutError), # Common network errors
    retry_kwargs={'max_retries': 3, 'countdown': 60} # Retry 3 times, wait 60s
)
def delete_storage_object_task(self: Task, object_storage_uri: str):
    """Deletes an object from S3/MinIO storage."""
    task_id = self.request.id
    logger.info(f"Task {task_id}: Received request to delete object: {object_storage_uri}")

    if not object_storage_uri or not object_storage_uri.startswith("s3://"):
        logger.warning(f"Task {task_id}: Invalid or missing object storage URI: '{object_storage_uri}'. Ignoring.")
        # Use Ignore() to prevent Celery treating this as a failure needing retry
        raise Ignore()

    try:
        storage_options = settings.s3_storage_options
        fs = s3fs.S3FileSystem(**storage_options)
        s3_path = object_storage_uri.replace("s3://", "")

        if fs.exists(s3_path):
            logger.info(f"Task {task_id}: Object found. Deleting {object_storage_uri}...")
            fs.rm(s3_path)
            logger.info(f"Task {task_id}: Successfully deleted object: {object_storage_uri}")
            return {"status": "deleted", "uri": object_storage_uri}
        else:
            logger.warning(f"Task {task_id}: Object not found at {object_storage_uri}, no deletion performed.")
            # Consider this a success from the task's perspective (object is gone)
            return {"status": "not_found", "uri": object_storage_uri}

    except FileNotFoundError: # Might be raised by s3fs if bucket/path is weird
        logger.warning(f"Task {task_id}: Object or path not found for deletion: {object_storage_uri}.")
        raise Ignore() # Don't retry if file definitely doesn't exist
    except s3fs.errors.S3PermissionError as e: # Example specific error
         logger.error(f"Task {task_id}: Permission error deleting {object_storage_uri}: {e}")
         raise Ignore() # Don't retry permission errors
    except Exception as e:
        logger.error(f"Task {task_id}: Failed to delete object {object_storage_uri}: {e}", exc_info=True)
        # Let autoretry handle configured exceptions, raise others
        raise e # Re-raise other errors for Celery default handling/retry logic
    