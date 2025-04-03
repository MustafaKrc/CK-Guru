# worker/app/tasks/feature_extraction.py
import logging
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import git
import pandas as pd
from celery import Task
from git import Repo, GitCommandError
from sqlalchemy import select

from ...core.config import settings
from ...db.session import get_worker_sync_session
from shared.db.models.ck_metric import CKMetric
from shared.db.models.commit_guru_metric import CommitGuruMetric
from ..utils.commit_guru_utils import GitCommitLinker, calculate_commit_guru_metrics
from ..utils.git_utils import determine_default_branch, checkout_commit
from ..utils.github_utils import GitHubIssueFetcher, extract_issue_ids, extract_repo_owner_name
from ..utils.task_utils import update_task_state


logger = logging.getLogger(__name__)
CK_JAR_PATH = Path('/app/third_party/ck.jar')

def _run_ck_tool(repo_dir: Path, commit_hash: str) -> pd.DataFrame:
    """
    Runs the CK tool, handling its quirky output file naming by passing
    a file prefix within a temporary directory.

    Args:
        repo_dir: Path to the checked-out repository.
        commit_hash: The commit being analyzed.

    Returns:
        DataFrame containing the CK class metrics, or empty DataFrame on error.
    """
    use_jars = "false"
    max_files_per_partition = 0
    variables_and_fields = "false"
    metrics_df = pd.DataFrame()

    if not CK_JAR_PATH.exists():
        logger.error(f"CK JAR not found at {CK_JAR_PATH}")
        raise FileNotFoundError(f"CK JAR not found at {CK_JAR_PATH}")

    try:
        # Create a temporary directory to contain the uniquely prefixed output files
        with tempfile.TemporaryDirectory(prefix=f"ck_run_{commit_hash}_") as temp_dir_name:
            temp_dir_path = Path(temp_dir_name)
            logger.info(f"Using temporary directory for CK run: {temp_dir_path}")

            # --- Construct the FILE PREFIX for CK ---
            # Use a unique name within the temp dir to avoid collisions if CK somehow
            # ignores the full path part (less likely but safe)
            output_file_prefix = temp_dir_path / f"ck_output_{commit_hash}_"
            logger.info(f"Passing output prefix to CK: {output_file_prefix}")

            # --- Expected output file paths based on the prefix ---
            expected_class_csv_path = Path(f"{output_file_prefix}class.csv")
            expected_method_csv_path = Path(f"{output_file_prefix}method.csv") # And others if needed

            # --- Run CK with the output file prefix ---
            try:
                logger.info(f"Running CK for commit {commit_hash} on {repo_dir}...")
                command = [
                    'java', '-jar', str(CK_JAR_PATH), str(repo_dir),
                    use_jars, str(max_files_per_partition), variables_and_fields,
                    str(output_file_prefix) # <<< PASS THE PREFIX HERE
                ]
                logger.debug(f"Executing command: {' '.join(command)}")

                completed_process = subprocess.run(
                    command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1200
                )
                logger.debug(f"CK stdout for {commit_hash}:\n{completed_process.stdout.decode()}")
                if completed_process.stderr:
                     # Log stderr but don't necessarily treat log4j warnings as errors
                     stderr_output = completed_process.stderr.decode()
                     if "Exception" in stderr_output or "Error" in stderr_output: # Look for actual errors
                         logger.error(f"CK stderr reported errors for {commit_hash}:\n{stderr_output}")
                     else:
                          logger.warning(f"CK stderr for {commit_hash}:\n{stderr_output}") # Likely just log4j noise

            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, Exception) as e:
                 # Log specific errors
                if isinstance(e, subprocess.CalledProcessError):
                    error_msg = f"Error running CK (exit code {e.returncode}) for {commit_hash}: {e.stderr.decode()}"
                elif isinstance(e, subprocess.TimeoutExpired):
                    error_msg = f"CK timed out for commit {commit_hash}."
                else:
                    error_msg = f"Unexpected error during CK subprocess for {commit_hash}: {e}"
                logger.error(error_msg, exc_info=isinstance(e, Exception) and not isinstance(e, (subprocess.CalledProcessError, subprocess.TimeoutExpired)))
                return pd.DataFrame() # Temp dir cleaned by context manager

            # --- Process CK Output: Check for the prefixed file ---
            if expected_class_csv_path.is_file():
                logger.info(f"Found expected CK output file: {expected_class_csv_path}")
                try:
                    metrics_df = pd.read_csv(expected_class_csv_path)
                    logger.info(f"Successfully read {len(metrics_df)} CK metrics for {commit_hash}.")
                except pd.errors.EmptyDataError:
                     logger.warning(f"CK output file {expected_class_csv_path} is empty for {commit_hash}.")
                     metrics_df = pd.DataFrame()
                except Exception as e:
                     logger.error(f"Error reading CK output CSV {expected_class_csv_path} for {commit_hash}: {e}")
                     metrics_df = pd.DataFrame()
                finally:
                    # Clean up the specific output files manually since they might
                    # be directly in the temp dir now (TemporaryDirectory cleans the dir itself)
                    try:
                        if expected_class_csv_path.exists(): os.remove(expected_class_csv_path)
                        if expected_method_csv_path.exists(): os.remove(expected_method_csv_path)
                        # Remove other potential prefixed files (variable.csv etc.)
                    except OSError as rm_err:
                         logger.error(f"Error removing CK output files like {expected_class_csv_path}: {rm_err}")
            else:
                logger.error(f"CK class output file NOT found at expected path: {expected_class_csv_path}")
                # Check if maybe it DID create a directory despite the prefix (unlikely based on description)
                fallback_dir = Path(str(output_file_prefix)) # Check if a dir named like the prefix exists
                fallback_csv = fallback_dir / 'class.csv'
                if fallback_csv.is_file():
                     logger.error("CK created a DIRECTORY instead of using prefix! Trying to read from there.")
                     # Attempt to read from fallback (logic would be similar to above)
                     # metrics_df = pd.read_csv(fallback_csv) etc...
                # else: # No file found at all

        # --- Temporary directory is automatically cleaned up here ---
        logger.debug(f"Temporary directory {temp_dir_name} and its contents automatically cleaned up.")

    except Exception as outer_e:
        logger.error(f"Error during temporary directory handling for {commit_hash}: {outer_e}", exc_info=True)
        return pd.DataFrame()

    return metrics_df

def prepare_repository(task_id: str, git_url: str, repo_local_path: Path) -> git.Repo:
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

def _fetch_and_process_github_issues(
    task_id: str,
    git_url: str,
    commits_data: List[Dict[str, Any]]
) -> None:
    """
    Fetches GitHub issue data for commits mentioning issues IN PLACE.
    Modifies the `commits_data` list by adding GitHub info.
    Handles rate limiting internally via GitHubIssueFetcher.
    """
    logger.info(f"Task {task_id}: Starting GitHub issue processing...")
    repo_info = extract_repo_owner_name(git_url)
    if not repo_info:
        logger.warning(f"Task {task_id}: Cannot process GitHub issues, failed to extract owner/repo from URL: {git_url}")
        return
    owner, repo_name = repo_info

    if not settings.GITHUB_TOKEN:
        logger.warning(f"Task {task_id}: Skipping GitHub issue processing - GITHUB_TOKEN not set.")
        return

    fetcher = GitHubIssueFetcher()
    processed_count = 0
    total_commits = len(commits_data)

    for commit in commits_data:
        commit_hash_short = commit.get('commit_hash', 'UNKNOWN')[:7]
        message = commit.get('commit_message')
        issue_ids = extract_issue_ids(message)

        if issue_ids:
            logger.debug(f"Task {task_id}: Found issue IDs {issue_ids} in commit {commit_hash_short}")
            commit['github_issue_ids'] = {"ids": issue_ids}

            try:
                # --- This call now handles rate limit waits internally ---
                earliest_ts = fetcher.get_earliest_issue_open_timestamp(owner, repo_name, issue_ids)
                # --- Removed GitHubRateLimitError handling here ---

                if earliest_ts is not None:
                    commit['github_earliest_issue_open_timestamp'] = earliest_ts
                    logger.debug(f"Task {task_id}: Earliest issue timestamp for {commit_hash_short}: {earliest_ts}")
                elif earliest_ts is None and issue_ids: # Check if fetch failed for existing IDs
                    logger.warning(f"Task {task_id}: Failed to fetch earliest timestamp for issues {issue_ids} in commit {commit_hash_short} (check previous logs for errors/retries).")

            except Exception as e: # Catch other unexpected errors during timestamp processing
                logger.error(f"Task {task_id}: Unexpected error processing GitHub issues for commit {commit_hash_short}: {e}", exc_info=True)

        processed_count += 1
        if processed_count % 100 == 0:
             logger.info(f"Task {task_id}: Processed GitHub issues for {processed_count}/{total_commits} commits...")

    logger.info(f"Task {task_id}: Finished GitHub issue processing.")

def calculate_and_save_guru_metrics(
    task: Task,
    task_id: str,
    repository_id: int,
    repo_local_path: Path,
    git_url: str 
) -> Tuple[int, List[Dict[str, Any]], str | None]: # Return inserted count, data list, warning
    """Calculates, links, fetches issue data, and saves Commit Guru metrics."""

    # --- Calculate Metrics ---
    update_task_state(task, 'STARTED', 'Calculating Commit Guru metrics...', 20)
    logger.info(f"Task {task_id}: Calculating Commit Guru metrics...")
    try:
        commit_guru_data_list = calculate_commit_guru_metrics(repo_local_path)
    except Exception as e:
        logger.error(f"Task {task_id}: Failed during Commit Guru metric calculation: {e}", exc_info=True)
        raise

    total_commits_found = len(commit_guru_data_list)
    logger.info(f"Task {task_id}: Found {total_commits_found} commits for Commit Guru analysis.")
    update_task_state(task, 'STARTED', f'Found {total_commits_found} commits. Linking bugs & fetching issues...', 40)

    # --- Fetch GitHub Issue Data (Modifies commit_guru_data_list in place) ---
    _fetch_and_process_github_issues(task_id, git_url, commit_guru_data_list)
    # Note: Rate limit errors during issue fetch might cause subsequent steps to have incomplete data

    # --- Link Bugs ---
    logger.info(f"Task {task_id}: Identifying corrective commits and linking bugs...")

    # Prepare info for the linker: map corrective hash -> earliest issue timestamp
    corrective_commits_info: Dict[str, Optional[int]] = {}
    for commit in commit_guru_data_list:
        commit_hash = commit.get('commit_hash')
        # Use the 'fix' flag calculated earlier
        if commit.get('fix') and commit_hash:
            corrective_commits_info[commit_hash] = commit.get('github_earliest_issue_open_timestamp') # Will be None if no issue found

    logger.info(f"Task {task_id}: Found {len(corrective_commits_info)} potential corrective commits for linking.")

    bug_link_map: Dict[str, List[str]] = {}
    warning_msg = None
    if corrective_commits_info: # Check if there are any corrective commits
        try:
            linker = GitCommitLinker(repo_local_path)
            # Pass the dictionary with timestamps to the linker
            bug_link_map = linker.link_corrective_commits(corrective_commits_info)
            logger.info(f"Task {task_id}: Bug linking identified {len(bug_link_map)} potential bug-introducing commits.")
        except Exception as e:
            logger.error(f"Task {task_id}: Failed during bug linking: {e}", exc_info=True)
            warning_msg = 'Bug linking failed, proceeding...'
            update_task_state(task, 'STARTED', warning_msg, 45, warning=warning_msg)
    else:
        logger.info(f"Task {task_id}: No corrective commits found, skipping bug linking.")


    buggy_hashes_set = set(bug_link_map.keys())

    # --- Save Metrics ---
    update_task_state(task, 'STARTED', 'Saving Commit Guru metrics...', 50)
    inserted_count = _save_commit_guru_metrics(
        task, repository_id, commit_guru_data_list, bug_link_map, buggy_hashes_set
    )

    return inserted_count, commit_guru_data_list, warning_msg

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
                "author_email": commit_data.get('author_email'),
                "author_date": commit_data.get('author_date'), 
                "author_date_unix_timestamp": commit_data.get('author_date_unix_timestamp'),
                "commit_message": commit_data.get('commit_message'),
                "is_buggy": is_buggy,
                "fix": commit_data.get('fix'), 
                "fixing_commit_hashes": {"hashes": fixing_hashes} if fixing_hashes else None,
                "github_issue_ids": commit_data.get('github_issue_ids'), 
                "github_earliest_issue_open_timestamp": commit_data.get('github_earliest_issue_open_timestamp'),
                "files_changed": commit_data.get('files_changed'),
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
                update_task_state(task, 'STARTED', f'Saving Commit Guru metrics ({i+1}/{total_to_process})...', progress)

        # Final commit handled by context manager
    logger.info(f"Task {task.request.id}: Finished saving {inserted_count} new Commit Guru metric records.")
    return inserted_count

def run_ck_analysis(
    task: Task,
    repository_id: int,
    repo: git.Repo,
    repo_local_path: Path,
) -> int:
    """Runs CK analysis on all commits of the default branch."""
    task_id = task.request.id
    logger.info(f"Task {task_id}: Starting CK metric extraction for all relevant commits...")
    update_task_state(task, 'STARTED', 'Starting CK metric extraction...', 80)

    try:
        default_branch_ref_name = determine_default_branch(repo)
        logger.info(f"Task {task_id}: Iterating commits for CK from reference: {default_branch_ref_name}")

        # Checkout the branch for iter_commits and CK tool execution
        local_branch_name = default_branch_ref_name.split('/')[-1]
        target_ref = repo.remotes.origin.refs[local_branch_name] # Get the Ref object

        if local_branch_name in repo.heads:
             repo.heads[local_branch_name].set_tracking_branch(target_ref).checkout()
        else:
             repo.create_head(local_branch_name, target_ref).set_tracking_branch(target_ref).checkout()
        logger.info(f"Checked out {local_branch_name} for CK analysis.")

        commits_iterator = repo.iter_commits(rev=default_branch_ref_name)
    except (git.GitCommandError, ValueError, IndexError, AttributeError, Exception) as e:
        logger.error(f"Task {task_id}: Error setting up commit iteration or checkout for CK: {e}", exc_info=True)
        # Decide if CK failure is fatal - let's allow task to succeed without CK for now
        update_task_state(task, 'STARTED', 'CK setup failed, skipping CK analysis.', 98, warning="CK setup failed")
        return 0 # Return 0 inserted count

    processed_ck_count = 0
    inserted_ck_count = 0
    processed_hashes_this_run = set() # Avoid redundant processing if iterator yields duplicates

    try:
        total_commits_for_ck = sum(1 for _ in repo.iter_commits(rev=default_branch_ref_name))
        logger.info(f"Task {task_id}: Estimated {total_commits_for_ck} total commits for CK analysis.")
    except Exception as count_err:
         logger.warning(f"Task {task_id}: Could not estimate total commits for CK progress: {count_err}. Progress reporting will be less granular.")
         total_commits_for_ck = 0 # Indicate unknown total

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

            logger.info(f"Running CK analysis for commit: {ck_commit_hash[:7]} ({processed_ck_count}{f'/{total_commits_for_ck}' if total_commits_for_ck > 0 else ''})...")
            if not checkout_commit(repo, ck_commit_hash):
                logger.error(f"Failed to checkout commit {ck_commit_hash[:7]} for CK. Skipping.")
                continue

            metrics_df = _run_ck_tool(repo_local_path, ck_commit_hash)
            if metrics_df.empty:
                logger.warning(f"CK analysis yielded no metrics for commit {ck_commit_hash[:7]}.")
                continue

            # Process and insert CK metrics
            try:
                valid_attrs = {key for key in CKMetric.__mapper__.attrs.keys()}
                records = metrics_df.to_dict(orient='records')
                instances_to_add = []
                for record in records:

                    # *** PATH CORRECTION ***
                    original_file_path_str = record.get('file')
                    if original_file_path_str:
                        try:
                            absolute_file_path = Path(original_file_path_str)
                            # Ensure path is absolute and starts with the repo root
                            if absolute_file_path.is_absolute() and str(absolute_file_path).startswith(str(repo_local_path)):
                                relative_path = absolute_file_path.relative_to(repo_local_path)
                                # Store the relative path string
                                record['file'] = str(relative_path)
                                logger.debug(f"Converted CK path '{original_file_path_str}' to relative '{record['file']}'")
                            else:
                                # Path is already relative or outside the repo? Keep original but warn.
                                 logger.warning(
                                     f"CK metric file path '{original_file_path_str}' "
                                     f"in commit {ck_commit_hash[:7]} is not absolute or doesn't start "
                                     f"with repo root '{repo_local_path}'. Using original path."
                                 )
                        except (ValueError, TypeError) as path_err:
                             logger.error(
                                 f"Error processing CK file path '{original_file_path_str}' "
                                 f"for commit {ck_commit_hash[:7]}: {path_err}. Keeping original."
                             )
                    else:
                         logger.warning(f"Missing 'file' key in CK metric record for commit {ck_commit_hash[:7]}.")
                    
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

            # Update progress periodically (e.g., every 50 commits)
            if processed_ck_count % 50 == 0:
                 # Calculate progress based on total estimate if available
                 current_progress = 80 + int(18 * (processed_ck_count / total_commits_for_ck)) if total_commits_for_ck > 0 else 80
                 update_task_state(task, 'STARTED', f'Analyzing CK ({processed_ck_count}{f"/{total_commits_for_ck}" if total_commits_for_ck > 0 else ""} completed)...', current_progress)


    logger.info(f"Task {task_id}: Finished CK analysis. Inserted {inserted_ck_count} new CK metric records from {processed_ck_count} commits checked.")
    return inserted_ck_count # Return number inserted, not processed

def load_analyzed_commits(ck_output_dir: Path) -> Set[str]:
    """Loads analyzed commits by checking existing CSVs in the CK output folder."""
    analyzed = set()
    if not ck_output_dir.exists():
        ck_output_dir.mkdir(parents=True, exist_ok=True) # Ensure it exists
        return analyzed
    for filename in os.listdir(ck_output_dir):
        if filename.endswith('.csv'):
            commit_hash = filename.replace('.csv', '')
            analyzed.add(commit_hash)
    logger.info(f"Loaded {len(analyzed)} previously analyzed commits from {ck_output_dir}")
    return analyzed