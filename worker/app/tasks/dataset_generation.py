# worker/app/tasks/dataset_generation.py
import time
import traceback
from io import BytesIO
from pathlib import Path
import logging
import re
from typing import List, Optional, Type
import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from celery import shared_task, Task
from sqlalchemy import select, text, func, bindparam, ColumnElement
from sqlalchemy.orm import sessionmaker, Session, aliased, DeclarativeBase
from sqlalchemy.sql.selectable import Select
from sqlalchemy.engine import Connection
import sqlalchemy as sa

from ..core.config import settings
from ..db.session import get_worker_sync_session, sync_engine # Use sync session
from shared.db.models import Repository, Dataset, BotPattern, CommitGuruMetric, CKMetric
from shared.db.models.dataset import DatasetStatusEnum
from .utils.task_utils import update_task_state
from .data_processing.cleaning_rules import RULE_FUNCTION_MAP # Import rule map

logger = logging.getLogger(__name__)

# Define columns for CK metrics (adjust if CKMetric model attributes change)
# Note: Use model attribute names (e.g., class_name, type_, lcom_norm)
CK_METRIC_COLUMNS = [
    'file', 'class_name', 'type_', 'cbo', 'cboModified', 'fanin', 'fanout',
    'wmc', 'dit', 'noc', 'rfc', 'lcom', 'lcom_norm', 'tcc', 'lcc',
    'totalMethodsQty', 'staticMethodsQty', 'publicMethodsQty', 'privateMethodsQty',
    'protectedMethodsQty', 'defaultMethodsQty', 'visibleMethodsQty',
    'abstractMethodsQty', 'finalMethodsQty', 'synchronizedMethodsQty',
    'totalFieldsQty', 'staticFieldsQty', 'publicFieldsQty', 'privateFieldsQty',
    'protectedFieldsQty', 'defaultFieldsQty', 'finalFieldsQty',
    'synchronizedFieldsQty', 'nosi', 'loc', 'returnQty', 'loopQty',
    'comparisonsQty', 'tryCatchQty', 'parenthesizedExpsQty',
    'stringLiteralsQty', 'numbersQty', 'assignmentsQty', 'mathOperationsQty',
    'variablesQty', 'maxNestedBlocksQty', 'anonymousClassesQty',
    'innerClassesQty', 'lambdasQty', 'uniqueWordsQty', 'modifiers',
    'logStatementsQty'
]
# Columns from CommitGuruMetric (excluding relationships and JSON fields handled separately)
COMMIT_GURU_METRIC_COLUMNS = [
    'commit_hash', 'parent_hashes', 'author_name', 'author_email', 'author_date',
    'author_date_unix_timestamp', 'commit_message', 'is_buggy', 'fix',
    'files_changed', 'ns', 'nd', 'nf', 'entropy', 'la', 'ld', 'lt', 'ndev',
    'age', 'nuc', 'exp', 'rexp', 'sexp'
]

# --- Helper Functions ---

def get_bot_filter_condition(bot_patterns: List[BotPattern], model_alias: Type[DeclarativeBase]):
    """Builds SQLAlchemy filter conditions for bot authors using an alias."""
    conditions = []
    # Apply exclusions first
    for bp in bot_patterns:
        if bp.is_exclusion:
            # Use the alias provided
            col = getattr(model_alias, 'author_name') # Access attribute via alias
            if bp.pattern_type == 'exact':
                conditions.append(col == bp.pattern)
            elif bp.pattern_type == 'wildcard':
                 sql_pattern = bp.pattern.replace('%', '\\%').replace('_', '\\_').replace('*', '%')
                 conditions.append(col.like(sql_pattern))
            elif bp.pattern_type == 'regex':
                 conditions.append(col.regexp_match(bp.pattern))

    exclusion_condition = sa.or_(*conditions) if conditions else sa.false()

    conditions = []
    # Apply inclusions second
    for bp in bot_patterns:
        if not bp.is_exclusion:
            col = getattr(model_alias, 'author_name') # Use alias
            if bp.pattern_type == 'exact':
                conditions.append(col == bp.pattern)
            elif bp.pattern_type == 'wildcard':
                 sql_pattern = bp.pattern.replace('%', '\\%').replace('_', '\\_').replace('*', '%')
                 conditions.append(col.like(sql_pattern))
            elif bp.pattern_type == 'regex':
                 conditions.append(col.regexp_match(bp.pattern))

    inclusion_condition = sa.or_(*conditions) if conditions else sa.false()

    # Final filter logic remains the same
    if not any(not bp.is_exclusion for bp in bot_patterns):
         final_condition = sa.not_(exclusion_condition)
    else:
         final_condition = sa.not_(exclusion_condition) & inclusion_condition

    return final_condition


def _get_parent_ck_metrics(session: Session, current_metrics_batch: pd.DataFrame) -> pd.DataFrame:
    """
    Fetches parent CK metrics for a batch of current metrics.

    Args:
        session: The SQLAlchemy session.
        current_metrics_batch: DataFrame of current CK/CommitGuru metrics,
                               must include 'commit_hash', 'parent_hashes',
                               'repository_id', 'file', 'class_name'.

    Returns:
        DataFrame with parent CK metrics, indexed matching the input batch.
        Parent metrics are prefixed with 'parent_'. Includes '_parent_metric_found' boolean.
    """
    parent_data_map = {} # key: (repo_id, parent_hash, file, class_name), value: ck_metric_dict

    # Prepare lookup keys from the batch
    lookup_keys = set()
    batch_map = {} # Map original index to lookup keys
    for idx, row in current_metrics_batch.iterrows():
        parent_hashes_str = row.get('parent_hashes')
        # Simple approach: use the first parent if multiple exist (merge commit)
        parent_hash = parent_hashes_str.split()[0] if parent_hashes_str else None
        if parent_hash:
            key = (
                row['repository_id'],
                parent_hash,
                row['file'],
                row['class_name'] # Use the correct attribute name
            )
            lookup_keys.add(key)
            if idx not in batch_map: batch_map[idx] = []
            batch_map[idx].append(key) # Store key associated with original index


    if not lookup_keys:
        # Create an empty DataFrame with expected columns if no parents need lookup
        parent_cols = ['_parent_metric_found'] + [f"parent_{col}" for col in CK_METRIC_COLUMNS]
        return pd.DataFrame(columns=parent_cols, index=current_metrics_batch.index)


    # Bulk query for parent metrics using the collected keys
    # This requires crafting a query that can efficiently fetch based on composite keys
    # Using IN operator on tuples might work depending on DB backend support
    # Or construct a more complex OR condition
    # For simplicity here, we might iterate, but a bulk approach is better for performance
    logger.debug(f"Looking up parent metrics for {len(lookup_keys)} unique parent states.")

    # --- Alternative: Bulk query using OR conditions (potentially less optimal than tuple IN) ---
    filters = []
    for repo_id, phash, pfile, pclass in lookup_keys:
         filters.append(
             sa.and_(
                 CKMetric.repository_id == repo_id,
                 CKMetric.commit_hash == phash,
                 CKMetric.file == pfile,
                 CKMetric.class_name == pclass # Use correct attribute name
             )
         )

    if filters:
        parent_stmt = select(CKMetric).where(sa.or_(*filters))
        parent_results = session.execute(parent_stmt).scalars().all()

        # Populate the map
        for pm in parent_results:
            key = (pm.repository_id, pm.commit_hash, pm.file, pm.class_name)
            parent_data_map[key] = {col: getattr(pm, col, None) for col in CK_METRIC_COLUMNS}
        logger.debug(f"Found {len(parent_data_map)} parent metric records in DB.")
    # --- End Bulk Query ---


    # Assemble the result DataFrame
    parent_metrics_list = []
    for idx in current_metrics_batch.index:
        parent_metric = None
        found = False
        # Get the lookup keys associated with this original row
        keys_for_row = batch_map.get(idx, [])
        if keys_for_row:
             # Use the first key found in the map (assumes first parent)
             for key in keys_for_row:
                  if key in parent_data_map:
                       parent_metric = parent_data_map[key]
                       found = True
                       break # Found the first parent

        result_row = {'_parent_metric_found': found}
        if parent_metric:
            result_row.update({f"parent_{col}": parent_metric.get(col) for col in CK_METRIC_COLUMNS})
        else:
            # Fill with NaNs if parent not found
            result_row.update({f"parent_{col}": np.nan for col in CK_METRIC_COLUMNS})
        parent_metrics_list.append(result_row)

    parent_df = pd.DataFrame(parent_metrics_list, index=current_metrics_batch.index)
    return parent_df


def calculate_delta_metrics(batch_df: pd.DataFrame) -> pd.DataFrame:
    """Calculates d_* metrics by subtracting parent metrics from current metrics."""
    delta_df = batch_df.copy() # Start with the merged df (current + parent)

    for col in CK_METRIC_COLUMNS:
        current_col = col
        parent_col = f"parent_{col}"
        delta_col = f"d_{col}"

        if current_col in delta_df.columns and parent_col in delta_df.columns:
            # Ensure columns are numeric, coercing errors to NaN
            current_numeric = pd.to_numeric(delta_df[current_col], errors='coerce')
            parent_numeric = pd.to_numeric(delta_df[parent_col], errors='coerce')

            # Calculate delta only where both values are numeric
            delta_df[delta_col] = current_numeric - parent_numeric
            # Where parent was not found (_parent_metric_found is False), delta should be NaN or current value?
            # Let's make delta NaN if parent was missing or either value was non-numeric
            delta_df.loc[~delta_df['_parent_metric_found'] | current_numeric.isna() | parent_numeric.isna(), delta_col] = np.nan

        # Drop the intermediate parent column
        if parent_col in delta_df.columns:
             delta_df = delta_df.drop(columns=[parent_col])

    return delta_df


# --- Main Task ---

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
    output_file_path: Optional[Path] = None
    pq_writer: Optional[pq.ParquetWriter] = None
    total_rows_processed = 0
    total_rows_written = 0

    try:
        # Use a single synchronous session for the entire task
        with get_worker_sync_session() as session: # Use sync session manager

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

            # TODO: Add file type filtering (e.g., ckm.file.like('%.java')) if needed based on config

            # 4. Batch Processing with Streaming
            batch_size = 1000 # Adjust batch size based on memory/performance
            logger.info(f"Task {task_id}: Starting data processing in batches of {batch_size}...")

            # Set up output file path and Parquet writer
            output_dir = Path(settings.STORAGE_BASE_PATH) / "datasets"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file_path = output_dir / f"dataset_{dataset_id}.parquet"
            logger.info(f"Task {task_id}: Output file will be: {output_file_path}")

            first_batch = True
            arrow_schema = None

            # Use stream_results for memory efficiency
            conn: Connection = session.connection() # Get underlying DBAPI connection if needed by stream_results? or session.stream()
            stream = session.execute(base_query).yield_per(batch_size) # Use yield_per

            for i, result_batch in enumerate(stream.partitions(batch_size)):
                start_time_batch = time.time()
                if not result_batch: continue

                logger.debug(f"Task {task_id}: Processing batch {i+1}...")
                update_task_state(self, 'STARTED', f'Processing batch {i+1}...', 10 + int(80 * (i * batch_size) / (session.execute(select(func.count()).select_from(base_query.subquery())).scalar() or 1))) # Estimate progress

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

                # -- Calculate `changed_file_count` --
                # files_changed is already a list in CommitGuruMetric model if parsed correctly
                batch_df['changed_file_count'] = batch_df['files_changed'].apply(lambda x: len(x) if isinstance(x, list) else 0)
                # Calculate lines_per_file (example - needs refinement)
                batch_df['lines_per_file'] = (batch_df['la'].fillna(0) + batch_df['ld'].fillna(0)) / batch_df['changed_file_count'].replace(0, 1) # Avoid division by zero

                # -- Calculate Delta Metrics --
                logger.debug(f"Task {task_id}: Batch {i+1} - Calculating delta metrics...")
                parent_metrics_df = _get_parent_ck_metrics(session, batch_df)
                # Merge parent metrics - use left join to keep all rows from batch_df
                batch_df_merged = batch_df.join(parent_metrics_df)
                batch_df_with_deltas = calculate_delta_metrics(batch_df_merged)

                # -- Apply Configured Cleaning Rules --
                logger.debug(f"Task {task_id}: Batch {i+1} - Applying cleaning rules...")
                cleaned_batch_df = batch_df_with_deltas.copy() # Start with deltas calculated
                for rule_config in cleaning_rules_config:
                    rule_name = rule_config.get("name")
                    is_enabled = rule_config.get("enabled", False) # Default to disabled if flag missing
                    params = rule_config.get("params", {})

                    if is_enabled and rule_name in RULE_FUNCTION_MAP:
                        rule_func = RULE_FUNCTION_MAP[rule_name]
                        try:
                             logger.debug(f"Applying rule: {rule_name}")
                             if rule_name == 'rule_cluster_large_commits':
                                 # Pass dataset config for feature/target lists
                                 cleaned_batch_df = rule_func(cleaned_batch_df, params, dataset_config)
                             else:
                                 cleaned_batch_df = rule_func(cleaned_batch_df, params)
                             logger.debug(f"Rule {rule_name} applied. Shape after: {cleaned_batch_df.shape}")
                        except Exception as e:
                             logger.error(f"Error applying cleaning rule '{rule_name}' in batch {i+1}: {e}", exc_info=True)
                             # Optionally skip remaining rules for this batch or fail the task
                             # For now, continue processing the batch with potentially uncleaned data
                    elif is_enabled:
                         logger.warning(f"Rule '{rule_name}' is enabled but not found in RULE_FUNCTION_MAP.")


                # -- Filter Rows with Missing Parents --
                # If _parent_metric_found exists and is False, drop the row
                if '_parent_metric_found' in cleaned_batch_df.columns:
                     initial_rows = len(cleaned_batch_df)
                     cleaned_batch_df = cleaned_batch_df[cleaned_batch_df['_parent_metric_found'] != False]
                     dropped = initial_rows - len(cleaned_batch_df)
                     if dropped > 0:
                          logger.debug(f"Dropped {dropped} rows due to missing parent metrics.")

                # -- Feature Selection --
                # Ensure target column is included for potential use, even if not listed as a feature
                final_columns = list(set(feature_columns + ([target_column] if target_column else [])))
                # Only select columns that actually exist in the dataframe after processing
                available_final_columns = [col for col in final_columns if col in cleaned_batch_df.columns]
                if not available_final_columns:
                     logger.warning(f"Task {task_id}: Batch {i+1} - No requested feature/target columns remain after processing. Skipping batch write.")
                     continue

                final_batch_df = cleaned_batch_df[available_final_columns]

                # -- Append to Parquet File --
                if not final_batch_df.empty:
                    logger.debug(f"Task {task_id}: Batch {i+1} - Writing {len(final_batch_df)} rows to Parquet...")
                    table = pa.Table.from_pandas(final_batch_df, schema=arrow_schema, preserve_index=False)
                    if first_batch:
                        arrow_schema = table.schema # Infer schema from first batch
                        pq_writer = pq.ParquetWriter(output_file_path, arrow_schema)
                        first_batch = False

                    if pq_writer:
                         pq_writer.write_table(table)
                    else:
                         # This should not happen after the first batch unless the first batch was empty
                         logger.error("Parquet writer not initialized.")
                         raise IOError("Failed to initialize Parquet writer.")

                    total_rows_written += len(final_batch_df)

                batch_duration = time.time() - start_time_batch
                logger.debug(f"Task {task_id}: Batch {i+1} processed in {batch_duration:.2f} seconds.")
                # --- End Batch Loop ---

            # Close Parquet writer
            if pq_writer:
                pq_writer.close()
            logger.info(f"Task {task_id}: Finished processing {total_rows_processed} rows. Written {total_rows_written} rows to {output_file_path}.")

            # 5. Update Final Status
            dataset.status = DatasetStatusEnum.READY
            dataset.status_message = f"Dataset generated successfully. {total_rows_written} rows written."
            dataset.storage_path = str(output_file_path.relative_to(settings.STORAGE_BASE_PATH)) # Store relative path
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
            with get_worker_sync_session() as error_session:
                error_dataset = error_session.get(Dataset, dataset_id)
                if error_dataset:
                    error_dataset.status = DatasetStatusEnum.FAILED
                    # Truncate error message if too long for DB field
                    error_dataset.status_message = detailed_error[:1000] # Limit message length
                    error_session.commit()
        except Exception as db_update_err:
            logger.error(f"Task {task_id}: CRITICAL - Failed to update dataset status to FAILED in DB: {db_update_err}")

        # Clean up partially written file if it exists
        if output_file_path and output_file_path.exists():
            try:
                 logger.warning(f"Task {task_id}: Deleting partially generated file: {output_file_path}")
                 output_file_path.unlink()
            except OSError as unlink_err:
                 logger.error(f"Task {task_id}: Failed to delete partial file {output_file_path}: {unlink_err}")

        # Re-raise the exception so Celery marks the task as failed
        raise e

    finally:
         # Ensure Parquet writer is closed even if errors occurred before its definition
         if pq_writer:
              try:
                   pq_writer.close()
              except Exception as close_err:
                   logger.error(f"Task {task_id}: Error closing Parquet writer: {close_err}")