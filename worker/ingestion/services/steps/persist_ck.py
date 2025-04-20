# worker/ingestion/services/steps/persist_ck.py
import logging
import math
import pandas as pd
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

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
        total_commits_with_metrics = len(context.raw_ck_metrics)
        processed_commit_count = 0

        self._log_info(context, f"Persisting CK metrics for {total_commits_with_metrics} commits...")
        self._update_progress(context, f"Starting CK persistence for {total_commits_with_metrics} commits...", 0)

        with get_sync_db_session() as session:
            try:
                for commit_hash, metrics_df in context.raw_ck_metrics.items():
                    processed_commit_count += 1
                    if metrics_df.empty: continue

                    # Check if any metrics for this commit already exist to avoid duplicates
                    exists_stmt = select(CKMetric.id).where(
                        CKMetric.repository_id == context.repository_id,
                        CKMetric.commit_hash == commit_hash
                    ).limit(1)
                    if session.execute(exists_stmt).scalar_one_or_none() is not None:
                        # self._log_info(context, f"CK metrics for commit {commit_hash[:7]} already exist. Skipping.") # Too verbose
                        continue

                    instances_to_add = []
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

                            instances_to_add.append(CKMetric(**filtered))

                        except Exception as record_proc_err:
                             logger.error(f"Failed processing CK record for commit {commit_hash[:7]}: {record_proc_err}. Record: {record}", exc_info=False)
                             # Continue to next record

                    if instances_to_add:
                        session.add_all(instances_to_add)
                        inserted_count += len(instances_to_add)
                        # logger.debug(f"Added {len(instances_to_add)} CK records for commit {commit_hash[:7]} to session.")

                    # Update progress periodically (within the step's progress allocation)
                    if total_commits_with_metrics > 0 and processed_commit_count % 50 == 0:
                         step_progress = int(100 * (processed_commit_count / total_commits_with_metrics))
                         self._update_progress(context, f'Persisting CK ({processed_commit_count}/{total_commits_with_metrics})...', step_progress)

                session.commit() # Commit all CK metrics together

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