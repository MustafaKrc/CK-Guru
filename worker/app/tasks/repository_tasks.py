# worker/app/tasks/repository_tasks.py
import os
import shutil
import time
import logging
from pathlib import Path
from datetime import datetime

import pandas as pd
import git
from celery import shared_task, current_task
from celery.utils.log import get_task_logger
from sqlalchemy import select, exists
from sqlalchemy.exc import SQLAlchemyError

# --- Internal Imports ---
from ..core.config import settings
from .data_processing.feature_extraction import checkout_commit, run_ck_tool # Import the checkout and CK tool functions
from ..db.session import get_worker_sync_session  # Import the DB session context manager

# --- Setup Logger ---
logger = get_task_logger(__name__)

# Import the DB Model - **IMPORTANT**: Adjust path if models are shared differently
# Assuming models are defined in backend and accessible via PYTHONPATH or installed package
try:
    # This assumes 'backend' is structured such that 'app' is importable,
    # potentially requiring backend code to be installed in the worker
    # or adjusting PYTHONPATH in the worker container.
    from shared.db.models import CKMetric, Repository
except ModuleNotFoundError:
    logger.error("Could not import backend DB models. Ensure backend code is accessible.")
    # Fallback: Define a duplicate or simplified model here (less ideal)
    raise


# === Main Celery Task ===
@shared_task(bind=True, name='tasks.create_repository_dataset')
def create_repository_dataset_task(self, repository_id: int, git_url: str):
    """
    Celery task to clone repo, run CK metrics, and save results to the database.
    """
    task_id = self.request.id
    logger.info(f"Task {task_id}: Starting DB metric extraction for repo ID: {repository_id}, URL: {git_url}")

    # Define paths
    base_storage_path = Path(settings.STORAGE_BASE_PATH)
    repo_local_path = base_storage_path / "temp_clones" / f"repo_{repository_id}_{task_id}"
    # No longer need ck_metrics_output_dir for final CSVs

    repo = None
    total_metrics_inserted = 0

    try:
        # --- Ensure temp clone parent dir exists ---
        repo_local_path.parent.mkdir(parents=True, exist_ok=True)

        # --- Phase 1: Cloning ---
        logger.info(f"Task {task_id}: Cloning {git_url} to {repo_local_path}...")
        self.update_state(state='STARTED', meta={'status': 'Cloning repository...', 'progress': 5})
        if repo_local_path.exists():
             logger.warning(f"Task {task_id}: Cleaning up existing clone path {repo_local_path}...")
             shutil.rmtree(repo_local_path)
        repo = git.Repo.clone_from(git_url, repo_local_path, no_checkout=True)
        logger.info(f"Task {task_id}: Cloning complete.")

        # --- Phase 2: Iterate Commits and Run CK ---
        logger.info(f"Task {task_id}: Iterating commits and running CK analysis...")
        self.update_state(state='STARTED', meta={'status': 'Analyzing commits with CK...', 'progress': 20})

        COMMIT_LIMIT = 25 # Example limit
        # --- Dynamically determine the default branch ---
        default_branch_ref_name = None
        try:
            origin = repo.remotes.origin
            # Fetch remote refs to ensure origin/HEAD is up-to-date
            logger.debug(f"Task {task_id}: Fetching remote refs from origin...")
            origin.fetch()
            logger.debug(f"Task {task_id}: Fetch complete.")

            # Find the symbolic ref 'origin/HEAD'
            # It typically points to the default branch reference (e.g., origin/main)
            head_symref = next((ref for ref in origin.refs if ref.name == 'origin/HEAD'), None)

            if head_symref:
                # Resolve the symbolic ref to the actual reference (e.g., refs/remotes/origin/main)
                default_branch_ref = head_symref.reference
                default_branch_ref_name = default_branch_ref.name # e.g., 'origin/main'
                logger.info(f"Task {task_id}: Determined default branch reference via origin/HEAD: {default_branch_ref_name}")
            else:
                # Fallback if origin/HEAD is not found (less common)
                logger.warning(f"Task {task_id}: Could not find origin/HEAD symbolic ref. Trying common names (main, master)...")
                common_names_to_check = ['main', 'master'] # Add other common names if needed
                remote_ref_names = [r.name for r in origin.refs]
                for name in common_names_to_check:
                    if f'origin/{name}' in remote_ref_names:
                        default_branch_ref_name = f'origin/{name}'
                        logger.info(f"Task {task_id}: Using fallback default branch reference: {default_branch_ref_name}")
                        break
                if not default_branch_ref_name:
                    # If still not found, maybe try repo.active_branch (less reliable) or fail
                    active_branch_name = str(repo.active_branch) # Get current local branch name
                    default_branch_ref_name = f'origin/{active_branch_name}' # Assume origin exists
                    logger.warning(f"Task {task_id}: Using active local branch name as basis: {default_branch_ref_name}")
                    # Alternatively, raise an error here if a default MUST be found via common names/HEAD
                    # raise ValueError("Could not determine the default branch reference for the repository.")

            if not default_branch_ref_name:
                 raise ValueError("Ultimately failed to determine a default branch reference to iterate.")

            # --- Iterate using the determined reference name ---
            logger.info(f"Task {task_id}: Iterating commits from reference: {default_branch_ref_name}")
            commits_iterator = repo.iter_commits(rev=default_branch_ref_name, max_count=COMMIT_LIMIT)
            # --- End branch detection and iterator setup ---

        except (git.GitCommandError, ValueError, AttributeError, StopIteration) as e:
            logger.error(f"Task {task_id}: Error determining default branch or iterating commits: {e}", exc_info=True)
            self.update_state(state='FAILURE', meta={'status': 'Task failed', 'error': f"Failed to determine/iterate default branch: {e}", 'progress': 0})
            raise # Re-raise the exception to fail the task properly

        # Estimate total based on limit or actual count if needed (more expensive)
        total_commits_to_process = COMMIT_LIMIT
        processed_count = 0

        # Use the synchronous session context manager
        with get_worker_sync_session() as session: # Use SYNC session
            for commit in commits_iterator:
                processed_count += 1
                commit_hash = commit.hexsha
                parent_hash = commit.parents[0].hexsha if commit.parents else None

                commits_to_analyze_this_iteration = []

                # Check current commit (SYNC DB query)
                stmt_curr = select(exists().where(CKMetric.commit_hash == commit_hash, CKMetric.repository_id == repository_id))
                result_curr = session.execute(stmt_curr) 
                if not result_curr.scalar_one_or_none():
                    commits_to_analyze_this_iteration.append(commit_hash)
                else:
                     logger.debug(f"Metrics for commit {commit_hash} already exist in DB.")

                # Check parent commit (SYNC DB query)
                if parent_hash:
                    stmt_parent = select(exists().where(CKMetric.commit_hash == parent_hash, CKMetric.repository_id == repository_id))
                    result_parent = session.execute(stmt_parent) 
                    if not result_parent.scalar_one_or_none():
                        if parent_hash not in commits_to_analyze_this_iteration:
                             commits_to_analyze_this_iteration.append(parent_hash)
                    else:
                         logger.debug(f"Metrics for parent commit {parent_hash} already exist in DB.")

                # Analyze and Insert (Sync)
                for hash_to_analyze in commits_to_analyze_this_iteration:
                    logger.info(f"Analyzing commit: {hash_to_analyze} ({processed_count}/{total_commits_to_process})")
                    if checkout_commit(repo, hash_to_analyze): 
                        metrics_df = run_ck_tool(repo_local_path, hash_to_analyze) 
                        
                        if metrics_df.empty:
                            logger.warning(f"CK analysis yielded EMPTY DataFrame for commit {hash_to_analyze}.")
                            # Optionally 'continue' here if you don't want to proceed without metrics
                        else:
                            pass
                            #logger.info(f"CK DataFrame for {hash_to_analyze} has shape {metrics_df.shape}. Columns: {metrics_df.columns.tolist()}")

                        if not metrics_df.empty:
                            logger.info(f"Obtained {len(metrics_df)} metric rows for {hash_to_analyze}.")
                            try:
                                # Get valid Python attribute names directly from the SQLAlchemy model's mapper
                                # This is more robust than inspecting __table__.columns
                                valid_model_attributes = {key for key in CKMetric.__mapper__.attrs.keys()}
                                # logger.debug(f"Valid CKMetric model attributes: {valid_model_attributes}") # Optional debug

                                metrics_records = metrics_df.to_dict(orient='records')
                                instances_to_add = []

                                for original_record in metrics_records:
                                    # Start with a copy of the original data
                                    record_for_model = original_record.copy()

                                    # --- Handle Explicit Renames (Keywords/Invalid Chars) ---
                                    if 'class' in record_for_model:
                                        record_for_model['class_name'] = record_for_model.pop('class')
                                    if 'type' in record_for_model:
                                        record_for_model['type_'] = record_for_model.pop('type')
                                    if 'lcom*' in record_for_model:
                                        record_for_model['lcom_norm'] = record_for_model.pop('lcom*')
                                    # --- End Renames ---

                                    # Add repository_id and commit_hash
                                    record_for_model['repository_id'] = repository_id
                                    record_for_model['commit_hash'] = hash_to_analyze

                                    # Filter dict to only keys that are valid attributes in the CKMetric model
                                    filtered_record = {
                                        attr_name: value
                                        for attr_name, value in record_for_model.items()
                                        if attr_name in valid_model_attributes
                                    }

                                    # Handle potential NaN/Inf values AFTER filtering keys
                                    for attr_name, value in filtered_record.items():
                                        if isinstance(value, (float, int)):
                                            if pd.isna(value):
                                                filtered_record[attr_name] = None # Store NaN as NULL
                                            elif value == float('inf') or value == float('-inf'):
                                                logger.warning(f"Replacing infinity value for key '{attr_name}' in commit {hash_to_analyze}")
                                                filtered_record[attr_name] = None # Or handle appropriately
                                        # Optionally handle other type conversions if needed

                                    # logger.debug(f"Prepared filtered_record for {hash_to_analyze}: {filtered_record}")

                                    # Create the ORM instance using keyword arguments matching model attributes
                                    try:
                                        metric_instance = CKMetric(**filtered_record)
                                        instances_to_add.append(metric_instance)
                                    except TypeError as te:
                                        logger.error(f"TypeError creating CKMetric instance for commit {hash_to_analyze}. "
                                                    f"Data: {filtered_record}. Error: {te}")
                                        continue # Skip this record

                                if instances_to_add:
                                    session.add_all(instances_to_add)
                                    # Commit happens automatically via context manager exit
                                    total_metrics_inserted += len(instances_to_add)
                                    logger.info(f"Added {len(instances_to_add)} metric records for {hash_to_analyze} to DB session.")

                                else:
                                    # This might happen if all rows failed the TypeError check above or filtering removed everything
                                    logger.warning(f"No valid CKMetric instances prepared for commit {hash_to_analyze} after filtering/validation.")

                            except SQLAlchemyError as db_ins_err:
                                logger.error(f"Database error inserting metrics for {hash_to_analyze}: {db_ins_err}", exc_info=True)
                                # Session rollback will happen in context manager
                                raise # Propagate error to fail the task
                            except Exception as e:
                                logger.error(f"Error processing metrics DataFrame for {hash_to_analyze}: {e}", exc_info=True)
                                raise # Propagate error
                        else:
                            logger.warning(f"CK analysis yielded no metrics for commit {hash_to_analyze}.")
                    else:
                        logger.error(f"Failed to checkout commit {hash_to_analyze}. Skipping analysis.")

                # Update progress
                if processed_count % 20 == 0:
                    progress = 20 + int(75 * (processed_count / total_commits_to_process))
                    self.update_state(state='STARTED', meta={'status': f'Analyzing commits ({processed_count}/{total_commits_to_process})...', 'progress': progress})

            # End of loop - session commit happens automatically if no errors

        logger.info(f"Task {task_id}: Finished iterating commits. Inserted {total_metrics_inserted} new metric records.")
        self.update_state(state='STARTED', meta={'status': 'Finalizing...', 'progress': 98})

        # --- Return Success ---
        result_payload = {
            'status': 'Completed successfully',
            'repository_id': repository_id,
            'metrics_inserted_this_run': total_metrics_inserted,
            'total_commits_scanned_limit': COMMIT_LIMIT,
        }
        logger.info(f"Task {task_id}: DB Metric extraction completed successfully for repo ID: {repository_id}")
        self.update_state(state='SUCCESS', meta=result_payload) # Final update via context manager commit
        return result_payload

    # Keep existing error handling and finally block for clone cleanup
    except git.GitCommandError as e:
        error_message = f"Git command failed: {e.stderr or e}"
        logger.error(f"Task {task_id}: {error_message}", exc_info=True)
        self.update_state(state='FAILURE', meta={'status': 'Task failed', 'error': error_message, 'progress': 0})
        raise
    except SQLAlchemyError as db_err: # Catch DB errors from session context manager
        error_message = f"Database error during task execution: {db_err}"
        logger.error(f"Task {task_id}: {error_message}", exc_info=True)
        self.update_state(state='FAILURE', meta={'status': 'Task failed', 'error': error_message, 'progress': 0})
        raise
    except Exception as e:
        error_message = f"An unexpected error occurred: {str(e)}"
        logger.error(f"Task {task_id}: {error_message}", exc_info=True)
        self.update_state(state='FAILURE', meta={'status': 'Task failed', 'error': error_message, 'progress': 0})
        raise
    finally:
        if repo_local_path.exists():
            logger.info(f"Task {task_id}: Cleaning up temporary clone at {repo_local_path}...")
            try:
                shutil.rmtree(repo_local_path, ignore_errors=True)
                logger.info(f"Task {task_id}: Temporary clone cleanup finished.")
            except Exception as e:
                logger.error(f"Task {task_id}: Error removing directory {repo_local_path}: {e}", exc_info=True)