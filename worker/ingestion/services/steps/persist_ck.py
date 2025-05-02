# worker/ingestion/services/steps/persist_ck.py
import logging
import math
import pandas as pd
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .base import IngestionStep, IngestionContext
from shared.db_session import get_sync_db_session
from shared.db.models import CKMetric
from shared.core.config import settings

logger = logging.getLogger(__name__)
log_level = getattr(settings, 'LOG_LEVEL', 'INFO')
logger.setLevel(log_level.upper())

# Get valid CKMetric attribute names once
try:
    VALID_CK_ATTRS = {key for key in CKMetric.__mapper__.attrs.keys()}
except Exception:
     VALID_CK_ATTRS = set() # Fallback if inspection fails
     logger.error("Could not inspect CKMetric attributes for validation.")


class PersistCKMetricsStep(IngestionStep):
    name = "Persist CK Metrics"

    def execute(self, context: IngestionContext) -> IngestionContext:
        if not context.raw_ck_metrics:
            self._log_info(context, "No raw CK metrics data to persist.")
            return context

        inserted_count = 0
        total_commits_to_process = len(context.raw_ck_metrics)
        processed_commit_count = 0


        log_msg_prefix = f"Persisting CK metrics for {total_commits_to_process} commits..."
        if context.is_single_commit_mode:
            log_msg_prefix = f"Persisting CK metrics for single-commit mode ({total_commits_to_process} commits: target/parent)..."

        self._log_info(context, log_msg_prefix)
        self._update_progress(context, log_msg_prefix, 0)

        with get_sync_db_session() as session:
            try:
                all_instances_to_upsert = []
                for commit_hash, metrics_df in context.raw_ck_metrics.items():
                    processed_commit_count += 1
                    
                    if metrics_df.empty: 
                        continue

                    records = metrics_df.to_dict(orient='records')
                    for record in records:
                        try:
                            # --- Path Correction ---
                            record_file_path = None # Init to None
                            original_file_path_str = record.get('file')
                            if original_file_path_str:
                                try:
                                    absolute_file_path = Path(original_file_path_str)
                                    # Ensure path is absolute and starts with the repo root
                                    if absolute_file_path.is_absolute() and str(absolute_file_path).startswith(str(context.repo_local_path)):
                                        relative_path = absolute_file_path.relative_to(context.repo_local_path)
                                        record_file_path = str(relative_path) # Store relative path string
                                    else:
                                        # Path is already relative or outside the repo? Keep original but warn.
                                        # logger.warning(f"CK metric file path '{original_file_path_str}' in commit {commit_hash[:7]} not relative to repo root. Using original.")
                                        record_file_path = original_file_path_str # Use original
                                except (ValueError, TypeError) as path_err:
                                     logger.error(f"Error processing CK file path '{original_file_path_str}' for commit {commit_hash[:7]}: {path_err}. Using original.", exc_info=False)
                                     record_file_path = original_file_path_str # Use original on error

                            if record_file_path is None:
                                logger.warning(f"Missing or invalid 'file' key in CK metric record for commit {commit_hash[:7]}. Skipping record.")
                                continue # Skip record if file path is invalid/missing

                            # --- Attribute Mapping & Cleaning ---
                            record_clean = {}
                            record_clean['file'] = record_file_path # Use processed path
                            record_clean['class_name'] = record.pop('class', None) # Handle 'class' keyword
                            record_clean['type_'] = record.pop('type', None)       # Handle 'type' keyword
                            record_clean['lcom_norm'] = record.pop('lcom*', None) # Handle 'lcom*' name
                            record_clean['repository_id'] = context.repository_id
                            record_clean['commit_hash'] = commit_hash

                            # Copy other valid fields and clean NaN/Inf
                            for key, value in record.items():
                                if key in VALID_CK_ATTRS:
                                    if isinstance(value, float):
                                        if pd.isna(value) or math.isinf(value):
                                            record_clean[key] = None # Replace NaN/Inf with None
                                        else:
                                            record_clean[key] = value
                                    elif key not in record_clean: # Avoid overwriting mapped fields
                                         record_clean[key] = value

                            # Final filter to ensure only valid attributes remain
                            filtered = {k: v for k, v in record_clean.items() if k in VALID_CK_ATTRS}

                            all_instances_to_upsert.append(filtered)

                        except Exception as record_proc_err:
                             logger.error(f"Failed processing CK record for commit {commit_hash[:7]}: {record_proc_err}. Record: {record}", exc_info=False)
                             # Continue to next record

                    # Update progress periodically
                    if total_commits_to_process > 0 and processed_commit_count % 50 == 0:
                        step_progress = int(100 * (processed_commit_count / total_commits_to_process))
                        self._update_progress(context, f'Preparing CK ({processed_commit_count}/{total_commits_to_process})...', step_progress)

                 # --- Perform Bulk UPSERT ---
                if all_instances_to_upsert:
                    self._log_info(context, f"Attempting bulk UPSERT for {len(all_instances_to_upsert)} CK records...")

                    stmt = pg_insert(CKMetric).values(all_instances_to_upsert)

                    # Define columns to update on conflict
                    # Note: Using constraint name means index_elements isn't used here directly,
                    # but conceptually these are the columns *not* part of the unique key.
                    # You might want to be more explicit about which columns *should* be updated.
                    update_columns = {
                         col.name: col
                         for col in stmt.excluded # Use 'excluded' to refer to values proposed for insertion
                         # Filter which columns get updated - e.g., exclude id, repository_id, commit_hash, file, class_name?
                         if col.name not in ['id', 'repository_id', 'commit_hash', 'file', 'class_name']
                    }

                    # Create the ON CONFLICT DO UPDATE statement using the CONSTRAINT NAME
                    upsert_stmt = stmt.on_conflict_do_update(
                        constraint='uq_ck_metric_key',
                        set_=update_columns
                    )

                    result = session.execute(upsert_stmt) 
                    # rowcount might not be reliable for UPSERT across DBs/drivers
                    # We can't easily distinguish inserts vs updates here without more complex queries
                    # Log based on total attempted
                    self._log_info(context, f"Bulk UPSERT executed for {len(all_instances_to_upsert)} CK records.")
                    inserted_count = len(all_instances_to_upsert) # Assume all were potentially inserted/updated


                session.commit()

            except SQLAlchemyError as db_err:
                self._log_error(context, f"Database error during CK persistence: {db_err}", exc_info=True)
                session.rollback()
                raise # Re-raise critical DB error
            except Exception as e:
                self._log_error(context, f"Unexpected error during CK persistence: {e}", exc_info=True)
                session.rollback()
                raise # Re-raise other critical errors

        context.inserted_ck_metrics_count = inserted_count
        self._log_info(context, f"Persisted {inserted_count} CK metric records for {processed_commit_count} commits.")
        self._update_progress(context, "CK persistence complete.", 100) # Step complete
        return context