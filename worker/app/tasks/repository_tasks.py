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
from ..db.session import get_worker_session # Import the DB session context manager

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
async def create_repository_dataset_task(self, repository_id: int, git_url: str):
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

        COMMIT_LIMIT = 1000 # Example limit
        commits_iterator = repo.iter_commits(rev=repo.heads.master, max_count=COMMIT_LIMIT)
        total_commits_to_process = COMMIT_LIMIT
        processed_count = 0

        async with get_worker_session() as session: # Get DB session for the whole loop (or per commit)
            for commit in commits_iterator:
                processed_count += 1
                commit_hash = commit.hexsha
                parent_hash = commit.parents[0].hexsha if commit.parents else None

                commits_to_analyze_this_iteration = []
                # Check current commit
                stmt_curr = select(exists().where(CKMetric.commit_hash == commit_hash, CKMetric.repository_id == repository_id))
                result_curr = await session.execute(stmt_curr)
                if not result_curr.scalar_one_or_none():
                    commits_to_analyze_this_iteration.append(commit_hash)
                else:
                     logger.debug(f"Metrics for commit {commit_hash} already exist in DB.")

                # Check parent commit
                if parent_hash:
                    stmt_parent = select(exists().where(CKMetric.commit_hash == parent_hash, CKMetric.repository_id == repository_id))
                    result_parent = await session.execute(stmt_parent)
                    if not result_parent.scalar_one_or_none():
                        # Only add parent if not already added (could be the current commit of a previous iteration)
                        if parent_hash not in commits_to_analyze_this_iteration:
                             commits_to_analyze_this_iteration.append(parent_hash)
                    else:
                         logger.debug(f"Metrics for parent commit {parent_hash} already exist in DB.")

                # Analyze commits identified for this iteration
                for hash_to_analyze in commits_to_analyze_this_iteration:
                    logger.info(f"Analyzing commit: {hash_to_analyze} ({processed_count}/{total_commits_to_process})")
                    if checkout_commit(repo, hash_to_analyze):
                        # Pass a base temp dir for CK, it will manage subdirs internally now
                        metrics_df = run_ck_tool(repo_local_path, base_storage_path / "temp_ck_runs", hash_to_analyze)

                        if not metrics_df.empty:
                            logger.info(f"Obtained {len(metrics_df)} metric rows for {hash_to_analyze}.")
                            try:
                                # Prepare data for insertion
                                metrics_records = metrics_df.to_dict(orient='records')
                                instances_to_add = []
                                for record in metrics_records:
                                    # Map CK columns to DB model columns
                                    # Handle potential 'class' vs 'class_name'
                                    record['class_name'] = record.pop('class', None)
                                    # Handle potential 'lcom*' vs 'lcom_norm'
                                    if 'lcom*' in record:
                                         record['lcom_norm'] = record.pop('lcom*', None)

                                    # Add missing keys required by model
                                    record['repository_id'] = repository_id
                                    record['commit_hash'] = hash_to_analyze

                                    # Filter record to only include keys matching CKMetric columns
                                    # Prevents errors if CK outputs extra columns not in model
                                    valid_keys = {c.name for c in CKMetric.__table__.columns if c.name != 'id'}
                                    # Handle mapped columns ('class'->'class_name', 'lcom*'->'lcom_norm')
                                    mapped_keys = {'class': 'class_name', 'lcom*': 'lcom_norm'}
                                    filtered_record = {}
                                    for k, v in record.items():
                                        db_key = mapped_keys.get(k, k)
                                        if db_key in valid_keys:
                                             filtered_record[db_key] = v

                                    instances_to_add.append(CKMetric(**filtered_record))

                                if instances_to_add:
                                    session.add_all(instances_to_add)
                                    # Commit can happen outside the loop by the context manager
                                    # await session.flush() # Optional: Flush to check for immediate errors
                                    total_metrics_inserted += len(instances_to_add)
                                    logger.info(f"Added {len(instances_to_add)} metric records for {hash_to_analyze} to DB session.")

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