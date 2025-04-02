# worker/app/tasks/repository_tasks.py
import math
import os
import shutil
import time
import logging
from pathlib import Path
from datetime import datetime
import json
from typing import Dict, List, Any, Tuple, Optional, Set

import pandas as pd
import git
from celery import shared_task, Task # Import Task for type hinting self
from celery.utils.log import get_task_logger
from sqlalchemy import select, exists
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as DBSession # Alias to avoid confusion with task sessions

# --- Internal Imports ---
from ..core.config import settings
from .data_processing.feature_extraction import checkout_commit, run_ck_tool
from ..db.session import get_worker_sync_session
from .utils.commit_guru_utils import calculate_commit_guru_metrics, GitCommitLinker

# --- Setup Logger ---
logger = get_task_logger(__name__)

# --- Import DB Models ---
try:
    from shared.db.models import CKMetric, Repository, CommitGuruMetric
except ModuleNotFoundError:
    logger.critical("Could not import shared DB models. Ensure shared module is accessible.", exc_info=True)
    raise

# === Constants ===
CK_COMMIT_LIMIT = 5 # Example limit for CK analysis

# === Helper Functions ===

def _update_task_state(task: Task, state: str, status: str, progress: int, warning: Optional[str] = None):
    """Helper to update Celery task state."""
    meta = {'status': status, 'progress': progress}
    if warning:
        meta['warning'] = warning
    task.update_state(state=state, meta=meta)

def _prepare_repository(task_id: str, git_url: str, repo_local_path: Path) -> git.Repo:
    """Clones or updates the local repository."""
    if repo_local_path.exists():
        logger.info(f"Task {task_id}: Found existing clone at {repo_local_path}. Fetching updates...")
        try:
            repo = git.Repo(repo_local_path)
            repo.git.reset('--hard')
            repo.git.clean('-fdx')
            origin = repo.remotes.origin
            origin.fetch(prune=True) # Prune deleted remote branches
            logger.info(f"Task {task_id}: Fetch complete.")
            return repo
        except (git.GitCommandError, Exception) as e:
            logger.warning(f"Task {task_id}: Error updating existing repo at {repo_local_path}. Re-cloning. Error: {e}")
            shutil.rmtree(repo_local_path) # Clean up problematic clone
            # Fall through to clone
    # Clone if it doesn't exist or update failed
    logger.info(f"Task {task_id}: Cloning {git_url} to {repo_local_path}...")
    # Consider adding depth for large repos if full history isn't always needed immediately
    repo = git.Repo.clone_from(git_url, repo_local_path, no_checkout=True)
    logger.info(f"Task {task_id}: Cloning complete.")
    return repo

def _calculate_and_link_guru_metrics(
    task: Task,
    task_id: str,
    repo_local_path: Path
) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]], Set[str]]:
    """Calculates Commit Guru metrics and performs bug linking."""
    _update_task_state(task, 'STARTED', 'Calculating Commit Guru metrics...', 20)
    logger.info(f"Task {task_id}: Calculating Commit Guru metrics...")
    try:
        commit_guru_data_list = calculate_commit_guru_metrics(repo_local_path)
    except Exception as e:
        logger.error(f"Task {task_id}: Failed during Commit Guru metric calculation: {e}", exc_info=True)
        raise  # Re-raise to be caught by main handler

    total_commits_found = len(commit_guru_data_list)
    logger.info(f"Task {task_id}: Found {total_commits_found} commits for Commit Guru analysis.")
    _update_task_state(task, 'STARTED', f'Found {total_commits_found} commits. Linking bugs...', 40)

    logger.info(f"Task {task_id}: Identifying corrective commits and linking bugs...")
    corrective_hashes = {
        commit['commit_hash'] for commit in commit_guru_data_list
        if commit.get('fix') and commit.get('commit_hash')
    }
    logger.info(f"Task {task_id}: Found {len(corrective_hashes)} potential corrective commits.")

    bug_link_map: Dict[str, List[str]] = {}
    warning_msg = None
    if corrective_hashes:
        try:
            linker = GitCommitLinker(repo_local_path)
            bug_link_map = linker.link_corrective_commits(corrective_hashes)
            logger.info(f"Task {task_id}: Bug linking identified {len(bug_link_map)} potential bug-introducing commits.")
        except Exception as e:
            logger.error(f"Task {task_id}: Failed during bug linking: {e}", exc_info=True)
            warning_msg = 'Bug linking failed, proceeding with metrics...'
            _update_task_state(task, 'STARTED', warning_msg, 45, warning=warning_msg) # Update with warning

    buggy_hashes_set = set(bug_link_map.keys())
    _update_task_state(task, 'STARTED', 'Saving Commit Guru metrics...', 50)
    return commit_guru_data_list, bug_link_map, buggy_hashes_set

def _save_commit_guru_metrics(
    task: Task,
    repository_id: int,
    commit_guru_data_list: List[Dict[str, Any]],
    bug_link_map: Dict[str, List[str]],
    buggy_hashes_set: Set[str]
) -> int:
    """Saves Commit Guru metrics to the database, skipping existing ones."""
    logger.info(f"Task {task.request.id}: Saving Commit Guru metrics to database...")
    inserted_count = 0
    total_to_process = len(commit_guru_data_list)

    with get_worker_sync_session() as session:
        for i, commit_data in enumerate(commit_guru_data_list):
            commit_hash = commit_data.get('commit_hash')
            if not commit_hash:
                logger.warning(f"Skipping commit data entry due to missing hash: {commit_data.get('author_name')}")
                continue

            # Check existence efficiently
            exists_stmt = select(CommitGuruMetric.id).where(
                CommitGuruMetric.repository_id == repository_id,
                CommitGuruMetric.commit_hash == commit_hash
            ).limit(1)
            if session.execute(exists_stmt).scalar_one_or_none() is not None:
                continue # Skip if already exists

            # Prepare and insert
            is_buggy = commit_hash in buggy_hashes_set
            fixing_hashes = bug_link_map.get(commit_hash) if is_buggy else None
            metric_instance_data = {
                "repository_id": repository_id, "commit_hash": commit_hash,
                "parent_hashes": commit_data.get('parent_hashes'),
                "author_name": commit_data.get('author_name'),
                "author_date_unix_timestamp": commit_data.get('author_date_unix_timestamp'),
                "is_buggy": is_buggy,
                "author_email": commit_data.get('author_email'),
                "author_date": commit_data.get('author_date'),
                "commit_message": commit_data.get('commit_message'),
                "files_changed": commit_data.get('files_changed'),
                "fix": commit_data.get('fix'),
                "fixing_commit_hashes": {"hashes": fixing_hashes} if fixing_hashes else None,
                "ns": commit_data.get('ns'), "nd": commit_data.get('nd'),
                "nf": commit_data.get('nf'), "entropy": commit_data.get('entropy'),
                "la": commit_data.get('la'), "ld": commit_data.get('ld'),
                "lt": commit_data.get('lt'), "ndev": commit_data.get('ndev'),
                "age": commit_data.get('age'), "nuc": commit_data.get('nuc'),
                "exp": commit_data.get('exp'), "rexp": commit_data.get('rexp'),
                "sexp": commit_data.get('sexp'),
            }
            try:
                metric_instance = CommitGuruMetric(**metric_instance_data)
                session.add(metric_instance)
                inserted_count += 1
            except Exception as e:
                logger.error(f"Error creating CommitGuruMetric for {commit_hash[:7]}: {e}", exc_info=True)
                logger.debug(f"Data causing error: {metric_instance_data}")
                # Rely on session rollback via context manager

            # Update progress periodically
            if (i + 1) % 100 == 0:
                 progress = 50 + int(30 * ((i + 1) / total_to_process)) if total_to_process else 50
                 _update_task_state(task, 'STARTED', f'Saving Commit Guru metrics ({i+1}/{total_to_process})...', progress)

        # Final commit handled by context manager
    logger.info(f"Task {task.request.id}: Finished saving {inserted_count} new Commit Guru metric records.")
    return inserted_count

def _determine_default_branch(repo: git.Repo, task_id: str) -> str:
    """Determines the default branch name for CK analysis."""
    try:
        origin = repo.remotes.origin
        if not repo.heads and not origin.refs: # Handle empty repo
             logger.warning(f"Task {task_id}: No local heads or remote refs found. Fetching explicitly.")
             origin.fetch()

        remote_refs = {r.name: r for r in origin.refs} # Map name to ref object

        # Try common names first
        for name in ['origin/main', 'origin/master']:
            if name in remote_refs:
                logger.info(f"Task {task_id}: Using default branch: {name}")
                return name

        # Try origin/HEAD symbolic reference
        head_symref = remote_refs.get('origin/HEAD')
        if head_symref and hasattr(head_symref, 'reference'):
             ref_name = head_symref.reference.name
             logger.info(f"Task {task_id}: Determined default branch via origin/HEAD: {ref_name}")
             return ref_name

        # Last resort: pick the first available remote branch (excluding HEAD)
        available_refs = [name for name in remote_refs if name != 'origin/HEAD']
        if available_refs:
            fallback_ref = sorted(available_refs)[0] # Sort for some determinism
            logger.warning(f"Task {task_id}: Could not determine default branch (main/master/HEAD). Using fallback ref: {fallback_ref}")
            return fallback_ref
        else:
            raise ValueError("No suitable remote branch reference found for CK analysis.")

    except (git.GitCommandError, AttributeError, ValueError, Exception) as e:
        logger.error(f"Task {task_id}: Error determining default branch: {e}", exc_info=True)
        raise ValueError("Failed to determine default branch.") from e


def _run_ck_analysis(
    task: Task,
    repository_id: int,
    repo: git.Repo,
    repo_local_path: Path,
    commit_limit: int
) -> int:
    """Runs CK analysis on recent commits of the default branch."""
    task_id = task.request.id
    logger.info(f"Task {task_id}: Starting CK metric extraction (limit: {commit_limit})...")
    _update_task_state(task, 'STARTED', 'Starting CK metric extraction...', 80)

    try:
        default_branch_ref_name = _determine_default_branch(repo, task_id)
        logger.info(f"Task {task_id}: Iterating commits for CK from reference: {default_branch_ref_name}")

        # Checkout the branch for iter_commits and CK tool execution
        local_branch_name = default_branch_ref_name.split('/')[-1]
        target_ref = repo.remotes.origin.refs[local_branch_name] # Get the Ref object

        if local_branch_name in repo.heads:
             repo.heads[local_branch_name].set_tracking_branch(target_ref).checkout()
        else:
             repo.create_head(local_branch_name, target_ref).set_tracking_branch(target_ref).checkout()
        logger.info(f"Checked out {local_branch_name} for CK analysis.")

        commits_iterator = repo.iter_commits(rev=default_branch_ref_name, max_count=commit_limit)
    except (git.GitCommandError, ValueError, IndexError, AttributeError, Exception) as e:
        logger.error(f"Task {task_id}: Error setting up commit iteration or checkout for CK: {e}", exc_info=True)
        # Decide if CK failure is fatal - let's allow task to succeed without CK for now
        _update_task_state(task, 'STARTED', 'CK setup failed, skipping CK analysis.', 98, warning="CK setup failed")
        return 0 # Return 0 inserted count

    processed_ck_count = 0
    inserted_ck_count = 0
    processed_hashes_this_run = set() # Avoid redundant processing if iterator yields duplicates

    with get_worker_sync_session() as session:
        for commit in commits_iterator:
            ck_commit_hash = commit.hexsha
            if ck_commit_hash in processed_hashes_this_run:
                continue
            processed_hashes_this_run.add(ck_commit_hash)
            processed_ck_count += 1

            # Check existence
            exists_stmt = select(CKMetric.id).where(
                CKMetric.repository_id == repository_id,
                CKMetric.commit_hash == ck_commit_hash
            ).limit(1)
            if session.execute(exists_stmt).scalar_one_or_none() is not None:
                continue

            logger.info(f"Running CK analysis for commit: {ck_commit_hash[:7]} ({processed_ck_count}/{commit_limit})")
            if not checkout_commit(repo, ck_commit_hash):
                logger.error(f"Failed to checkout commit {ck_commit_hash[:7]} for CK. Skipping.")
                continue

            metrics_df = run_ck_tool(repo_local_path, ck_commit_hash)
            if metrics_df.empty:
                logger.warning(f"CK analysis yielded no metrics for commit {ck_commit_hash[:7]}.")
                continue

            # Process and insert CK metrics
            try:
                valid_attrs = {key for key in CKMetric.__mapper__.attrs.keys()}
                records = metrics_df.to_dict(orient='records')
                instances_to_add = []
                for record in records:
                    # Prepare record (handle renames, add IDs, filter, clean NaN/Inf)
                    record['class_name'] = record.pop('class', None)
                    record['type_'] = record.pop('type', None)
                    record['lcom_norm'] = record.pop('lcom*', None)
                    record['repository_id'] = repository_id
                    record['commit_hash'] = ck_commit_hash

                    filtered = {k: v for k, v in record.items() if k in valid_attrs}
                    for k, v in filtered.items():
                        if isinstance(v, float):
                            if pd.isna(v): filtered[k] = None
                            elif math.isinf(v):
                                logger.warning(f"Replacing Inf in CK metric '{k}' for {ck_commit_hash[:7]}")
                                filtered[k] = None
                    try:
                        instances_to_add.append(CKMetric(**filtered))
                    except TypeError as te:
                        logger.error(f"TypeError creating CKMetric for {ck_commit_hash[:7]}. Data: {filtered}. Error: {te}")

                if instances_to_add:
                    session.add_all(instances_to_add)
                    inserted_ck_count += len(instances_to_add)

            except Exception as e:
                logger.error(f"Error processing CK metrics DataFrame for {ck_commit_hash[:7]}: {e}", exc_info=True)

            # Update progress
            if processed_ck_count % 5 == 0:
                progress = 80 + int(18 * (processed_ck_count / commit_limit)) if commit_limit else 80
                _update_task_state(task, 'STARTED', f'Analyzing CK ({processed_ck_count}/{commit_limit})...', progress)

    logger.info(f"Task {task_id}: Finished CK analysis. Inserted {inserted_ck_count} new CK metric records.")
    return inserted_ck_count

# === Main Celery Task (Orchestrator) ===
@shared_task(bind=True, name='tasks.create_repository_dataset')
def create_repository_dataset_task(self: Task, repository_id: int, git_url: str):
    """
    Orchestrates the data extraction process for a repository:
    1. Prepare local clone.
    2. Calculate Commit Guru metrics & link bugs.
    3. Save Commit Guru metrics.
    4. Run CK analysis on recent commits.
    """
    task_id = self.request.id
    logger.info(f"Task {task_id}: Starting data extraction for repo ID: {repository_id}, URL: {git_url}")

    base_storage_path = Path(settings.STORAGE_BASE_PATH)
    repo_local_path = base_storage_path / "clones" / f"repo_{repository_id}"
    repo_local_path.parent.mkdir(parents=True, exist_ok=True)

    repo: Optional[git.Repo] = None
    commit_guru_data_list: List[Dict[str, Any]] = []
    bug_link_map: Dict[str, List[str]] = {}
    total_guru_metrics_inserted = 0
    total_ck_metrics_inserted = 0
    final_status = "Completed successfully"
    warning_info: Optional[str] = None

    try:
        # --- Phase 1: Prepare Repository ---
        _update_task_state(self, 'STARTED', 'Preparing repository...', 5)
        repo = _prepare_repository(task_id, git_url, repo_local_path)
        _update_task_state(self, 'STARTED', 'Repository ready.', 15)

        # --- Phase 2 & 3: Calculate Commit Guru Metrics & Link Bugs ---
        commit_guru_data_list, bug_link_map, buggy_hashes_set = _calculate_and_link_guru_metrics(
            self, task_id, repo_local_path
        )
        # Check if a warning was set during linking
        current_meta = self.AsyncResult(self.request.id).info or {}
        if 'warning' in current_meta:
             warning_info = current_meta['warning']
             final_status = "Completed with warnings (Bug linking failed)"


        # --- Phase 4: Save Commit Guru Metrics ---
        total_guru_metrics_inserted = _save_commit_guru_metrics(
            self, repository_id, commit_guru_data_list, bug_link_map, buggy_hashes_set
        )

        # --- Phase 5: Run CK Analysis ---
        if repo: # Ensure repo object is valid before CK
             total_ck_metrics_inserted = _run_ck_analysis(
                 self, repository_id, repo, repo_local_path, CK_COMMIT_LIMIT
             )
             # Check if CK phase added a warning
             current_meta = self.AsyncResult(self.request.id).info or {}
             if 'warning' in current_meta and not warning_info: # Avoid overwriting previous warning
                  warning_info = current_meta['warning']
                  final_status = "Completed with warnings (CK analysis issue)"
        else:
             logger.error(f"Task {task_id}: Skipping CK analysis because repository object is invalid.")
             final_status = "Completed with errors (Repo prep failed)" # Upgrade status


        # --- Final Update ---
        _update_task_state(self, 'STARTED', 'Finalizing...', 99) # Progress before final SUCCESS state

        result_payload = {
            'status': final_status,
            'repository_id': repository_id,
            'commit_guru_metrics_inserted': total_guru_metrics_inserted,
            'ck_metrics_inserted': total_ck_metrics_inserted,
            'total_commits_analyzed_guru': len(commit_guru_data_list),
            'ck_commit_limit': CK_COMMIT_LIMIT,
        }
        if warning_info:
            result_payload['warning'] = warning_info

        logger.info(f"Task {task_id}: Data extraction finished for repo ID: {repository_id}. Status: {final_status}")
        # Note: Celery automatically sets state to SUCCESS on successful return
        # self.update_state(state='SUCCESS', meta=result_payload) # Explicit SUCCESS state
        return result_payload

    except (git.GitCommandError, SQLAlchemyError, ValueError, Exception) as e:
        # Catch exceptions from helpers or main flow
        error_type = type(e).__name__
        error_message = f"Task failed due to {error_type}: {str(e)}"
        # Log critical for major failures
        if isinstance(e, (git.GitCommandError, SQLAlchemyError)):
             logger.critical(f"Task {task_id}: {error_message}", exc_info=True)
        else:
             logger.error(f"Task {task_id}: {error_message}", exc_info=True)

        # Update state to FAILURE
        try:
            # Check if self exists and has update_state method
             if hasattr(self, 'update_state') and callable(self.update_state):
                  self.update_state(state='FAILURE', meta={'status': 'Task failed', 'error': error_message, 'progress': 0})
        except Exception as update_err:
             logger.error(f"Task {task_id}: Failed to update task state to FAILURE: {update_err}")

        # Important: Re-raise the exception so Celery knows the task failed
        raise e