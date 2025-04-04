# worker/app/tasks/feature_extraction.py
import os
import math
import shutil
import logging
import tempfile
import subprocess
import dateutil.parser
from typing import Any, Dict, List, Optional, Set, Tuple
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
from celery import Task
from git import Repo, GitCommandError
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from shared.core.config import settings
from shared.db_session import get_sync_db_session
from shared.db.models.ck_metric import CKMetric
from shared.db.models.commit_guru_metric import CommitGuruMetric
from shared.db.models.github_issue import GitHubIssue
from shared.db.models.commit_github_issue_association import commit_github_issue_association_table
from shared.utils.commit_guru_utils import GitCommitLinker, calculate_commit_guru_metrics
from shared.utils.git_utils import determine_default_branch, checkout_commit
from shared.utils.github_utils import GitHubIssueFetcher, extract_issue_ids, extract_repo_owner_name, GitHubAPIResponse
from shared.utils.task_utils import update_task_state


logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

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

def prepare_repository(git_url: str, repo_local_path: Path) -> Repo:
    """Clones or updates the local repository."""
    if repo_local_path.exists():
        logger.info(f"Found existing clone at {repo_local_path}. Fetching updates...")
        try:
            repo = Repo(repo_local_path)
            repo.git.reset('--hard')
            repo.git.clean('-fdx')
            origin = repo.remotes.origin
            origin.fetch(prune=True) # Prune deleted remote branches
            logger.info(f"Fetch complete.")
            return repo
        except (GitCommandError, Exception) as e:
            logger.warning(f"Error updating existing repo at {repo_local_path}. Re-cloning. Error: {e}")
            shutil.rmtree(repo_local_path) # Clean up problematic clone
            # Fall through to clone
    # Clone if it doesn't exist or update failed
    logger.info(f"Cloning {git_url} to {repo_local_path}...")
    # Consider adding depth for large repos if full history isn't always needed immediately
    repo = Repo.clone_from(git_url, repo_local_path, no_checkout=True)
    logger.info(f"Cloning complete.")
    return repo

def _process_and_link_commit_issues(
    session: Session,
    repository_id: int,
    commit_metric_id: int, # The DB ID of the CommitGuruMetric record
    owner: str,
    repo_name: str,
    issue_numbers: List[str], # List of numbers like ['123', '45']
    fetcher: GitHubIssueFetcher
) -> List[int]:
    """
    Looks up, fetches (conditionally), updates/inserts GitHub issues in the DB,
    and links them to the given commit metric ID.

    Uses ETag caching. Handles API errors gracefully by potentially using stale data.

    Returns:
        List of database IDs of the GitHubIssue records successfully linked to the commit.
    """
    linked_issue_db_ids: List[int] = []
    now_utc = datetime.now(timezone.utc)

    for number_str in issue_numbers:
        try:
            issue_number = int(number_str)
        except ValueError:
            logger.warning(f"Invalid non-integer issue number '{number_str}' skipped for commit {commit_metric_id}")
            continue

        issue_db_id: Optional[int] = None
        issue_data_to_use: Optional[Dict[str, Any]] = None # Store data used for linking
        use_stale_data = False
        needs_linking = True # Assume we need to create the link unless proven otherwise

        # 1. DB Lookup
        stmt = select(GitHubIssue).where(
            GitHubIssue.repository_id == repository_id,
            GitHubIssue.issue_number == issue_number
        )
        # Fetch specific columns needed for decisions and potential use
        # stmt = stmt.options(load_only(GitHubIssue.id, GitHubIssue.etag, GitHubIssue.state, ...)) # Optimization
        db_issue: Optional[GitHubIssue] = session.execute(stmt).scalar_one_or_none()

        current_etag = db_issue.etag if db_issue else None

        # 2. Conditional API Fetch
        api_response: GitHubAPIResponse = fetcher.get_issue_data(
            owner, repo_name, number_str, current_etag=current_etag
        )

        # 3. Handle API Response and DB Update/Insert
        if db_issue:
            # --- Issue Found in DB ---
            issue_db_id = db_issue.id
            if api_response.status_code == 304: # Not Modified
                logger.debug(f"Issue #{issue_number} (DB ID: {issue_db_id}): ETag match (304). Updating last_fetched_at.")
                db_issue.last_fetched_at = now_utc # Update timestamp even if not modified
                session.add(db_issue) # Add to session to track update
                issue_data_to_use = {"id": issue_db_id, "state": db_issue.state} # Use existing data
            elif api_response.status_code == 200 and api_response.json_data: # Modified
                logger.info(f"Issue #{issue_number} (DB ID: {issue_db_id}): Data changed (200 OK). Updating DB.")
                new_data = api_response.json_data
                db_issue.state = new_data.get('state', 'unknown')
                db_issue.github_id = new_data.get('id')
                db_issue.api_url = new_data.get('url')
                db_issue.html_url = new_data.get('html_url')
                created_at = dateutil.parser.isoparse(new_data['created_at']).timestamp() if new_data.get('created_at') else None
                closed_at = dateutil.parser.isoparse(new_data['closed_at']).timestamp() if new_data.get('closed_at') else None
                db_issue.created_at_timestamp = int(created_at) if created_at is not None else None
                db_issue.closed_at_timestamp = int(closed_at) if closed_at is not None else None
                db_issue.etag = api_response.etag
                db_issue.last_fetched_at = now_utc
                session.add(db_issue)
                issue_data_to_use = {"id": issue_db_id, "state": db_issue.state} # Use newly updated data
            elif api_response.status_code in [404, 410]: # Gone / Deleted
                logger.warning(f"Issue #{issue_number} (DB ID: {issue_db_id}): Now missing on GitHub ({api_response.status_code}). Marking as deleted.")
                db_issue.state = 'deleted'
                db_issue.etag = None # Clear ETag
                db_issue.last_fetched_at = now_utc
                session.add(db_issue)
                issue_data_to_use = {"id": issue_db_id, "state": 'deleted'} # Use 'deleted' state
            else: # API Error (Rate limit, server error, etc.)
                logger.error(f"Issue #{issue_number} (DB ID: {issue_db_id}): API fetch failed (Status: {api_response.status_code}). Using stale data. Error: {api_response.error_message}")
                use_stale_data = True
                issue_data_to_use = {"id": issue_db_id, "state": db_issue.state} # Use existing stale data

        else:
            # --- Issue NOT Found in DB ---
            if api_response.status_code == 200 and api_response.json_data:
                logger.info(f"Issue #{issue_number}: Found on GitHub (200 OK). Inserting into DB.")
                new_data = api_response.json_data
                created_at = dateutil.parser.isoparse(new_data['created_at']).timestamp() if new_data.get('created_at') else None
                closed_at = dateutil.parser.isoparse(new_data['closed_at']).timestamp() if new_data.get('closed_at') else None
                new_issue = GitHubIssue(
                    repository_id=repository_id,
                    issue_number=issue_number,
                    github_id=new_data.get('id'),
                    state=new_data.get('state', 'unknown'),
                    created_at_timestamp=int(created_at) if created_at is not None else None,
                    closed_at_timestamp=int(closed_at) if closed_at is not None else None,
                    api_url=new_data.get('url'),
                    html_url=new_data.get('html_url'),
                    last_fetched_at=now_utc,
                    etag=api_response.etag
                )
                session.add(new_issue)
                session.flush() # Flush to get the new ID
                issue_db_id = new_issue.id
                issue_data_to_use = {"id": issue_db_id, "state": new_issue.state}
            elif api_response.status_code in [404, 410]:
                logger.warning(f"Issue #{issue_number}: Not found on GitHub ({api_response.status_code}). Skipping linking.")
                # Optionally insert a 'deleted' record here if desired to prevent future checks
                needs_linking = False
            else: # API Error
                logger.error(f"Issue #{issue_number}: API fetch failed for new issue (Status: {api_response.status_code}). Cannot link. Error: {api_response.error_message}")
                needs_linking = False


        # 4. Link Association (if issue DB ID is known and linking needed)
        if issue_db_id is not None and needs_linking:
            try:
                # Use PostgreSQL's ON CONFLICT DO NOTHING for efficiency
                # insert_stmt = pg_insert(commit_github_issue_association_table).values(
                #     commit_guru_metric_id=commit_metric_id,
                #     github_issue_id=issue_db_id
                # )
                # Specify the constraint name for ON CONFLICT target
                # Assuming the PK constraint is named 'commit_github_issue_association_pkey'
                # Adjust if your naming convention is different
                # If you don't know the name, you might target columns: ON CONFLICT (col1, col2)
                # Check your actual constraint name after migration.
                # Default name is usually tablename_pkey
                # do_nothing_stmt = insert_stmt.on_conflict_do_nothing(
                #     constraint='commit_github_issue_association_pkey'
                # )
                # session.execute(do_nothing_stmt)
                # linked_issue_db_ids.append(issue_db_id)
                # logger.debug(f"Linked commit {commit_metric_id} to issue #{issue_number} (DB ID: {issue_db_id})")

                # --- OR --- Check existence ORM approach (less efficient but maybe simpler):
                link_exists = session.query(commit_github_issue_association_table).filter_by(
                    commit_guru_metric_id=commit_metric_id,
                    github_issue_id=issue_db_id
                ).count() > 0
                if not link_exists:
                    # Need the CommitGuruMetric object to append to relationship
                    commit_metric_obj = session.get(CommitGuruMetric, commit_metric_id)
                    issue_obj = session.get(GitHubIssue, issue_db_id) # Get managed objects
                    if commit_metric_obj and issue_obj:
                         commit_metric_obj.github_issues.append(issue_obj)
                         session.add(commit_metric_obj) # Ensure change is tracked
                         linked_issue_db_ids.append(issue_db_id)
                         logger.debug(f"Linked commit {commit_metric_id} to issue #{issue_number} (DB ID: {issue_db_id}) via ORM")

            except Exception as link_err:
                 logger.error(f"Failed to link commit {commit_metric_id} to issue DB ID {issue_db_id}: {link_err}", exc_info=True)
                 session.rollback() # Rollback partial changes within this issue processing
                 # Decide whether to continue with other issues or re-raise
                 # For now, log and continue


    # Commit the session changes *after processing all issues for this commit*
    # Moved commit logic outside this helper to the main loop

    return linked_issue_db_ids

def _get_earliest_linked_issue_timestamp(session: Session, commit_metric_id: int) -> Optional[int]:
    """Queries the DB for the minimum created_at_timestamp among issues linked to a commit."""
    stmt = (
        select(func.min(GitHubIssue.created_at_timestamp))
        .join(commit_github_issue_association_table, GitHubIssue.id == commit_github_issue_association_table.c.github_issue_id)
        .where(commit_github_issue_association_table.c.commit_guru_metric_id == commit_metric_id)
        .where(GitHubIssue.created_at_timestamp.isnot(None)) # Ensure we only consider issues with a timestamp
    )
    earliest_ts = session.execute(stmt).scalar_one_or_none()
    return earliest_ts

def calculate_and_save_guru_metrics(
    task: Task,
    repository_id: int,
    repo_local_path: Path,
    git_url: str 
) -> Tuple[int, List[Dict[str, Any]], str | None]: # Return inserted count, data list, warning
    """
    Calculates Commit Guru metrics, processes/links GitHub issues using DB cache,
    identifies bug links, and saves metrics to the database.
    """

    task_id = task.request.id

    # --- Extract Owner/Repo ---
    repo_info = extract_repo_owner_name(git_url)
    if not repo_info:
        msg = f"Cannot process GitHub issues, failed to extract owner/repo from URL: {git_url}"
        logger.error(msg)
        # Decide: fail task or proceed without issue linking? Let's proceed with warning.
        update_task_state(task, 'STARTED', 'Owner/Repo extraction failed. Skipping issue linking.', 40, warning=msg)
        owner, repo_name = None, None
    else:
        owner, repo_name = repo_info

    # --- Calculate Metrics ---
    update_task_state(task, 'STARTED', 'Calculating Commit Guru metrics...', 20)
    logger.info(f"Task {task_id}: Calculating Commit Guru metrics...")
    try:
        # This function calculates the raw metrics from git log
        commit_guru_raw_data_list = calculate_commit_guru_metrics(repo_local_path)
    except Exception as e:
        logger.error(f"Task {task_id}: Failed during Commit Guru metric calculation: {e}", exc_info=True)
        raise

    total_commits_found = len(commit_guru_raw_data_list)
    if not total_commits_found:
        logger.info(f"Task {task_id}: No commits found by Commit Guru. Nothing to save.")
        update_task_state(task, 'STARTED', 'No commits found by Commit Guru.', 95)
        return 0, [], None # Return empty list for raw data

    logger.info(f"Task {task_id}: Found {total_commits_found} commits for Commit Guru analysis.")
    update_task_state(task, 'STARTED', f'Found {total_commits_found} commits. Processing issues & saving...', 40)

    # --- Initialize GitHub Fetcher ---
    # Pass token from settings
    fetcher = GitHubIssueFetcher(token=settings.GITHUB_TOKEN)

    # --- Save Metrics & Process Issues Iteratively ---
    inserted_count = 0
    processed_count = 0
    # Store commit_metric_id -> list of linked issue DB IDs
    commit_to_linked_issues_map: Dict[int, List[int]] = {}
    # Store commit_hash -> commit_metric_id for bug linking phase
    commit_hash_to_id_map: Dict[str, int] = {}
    # Store commit_hash -> is_fix_keyword_present
    commit_fix_keyword_map: Dict[str, bool] = {}

    with get_sync_db_session() as session:
        try:
            for i, raw_commit_data in enumerate(commit_guru_raw_data_list):
                processed_count += 1
                commit_hash = raw_commit_data.get('commit_hash')
                if not commit_hash:
                    logger.warning(f"Skipping raw commit data entry due to missing hash: {raw_commit_data.get('author_name')}")
                    continue

                commit_hash_to_id_map[commit_hash] = -1 # Placeholder ID initially
                commit_fix_keyword_map[commit_hash] = raw_commit_data.get('fix', False)

                # Check existence efficiently before creating ORM object
                exists_stmt = select(CommitGuruMetric.id).where(
                    CommitGuruMetric.repository_id == repository_id,
                    CommitGuruMetric.commit_hash == commit_hash
                ).limit(1)
                existing_id = session.execute(exists_stmt).scalar_one_or_none()

                if existing_id is not None:
                    commit_hash_to_id_map[commit_hash] = existing_id # Store existing ID
                    # Still need to potentially link issues even if metric exists
                    # Extract issues and link if owner/repo known
                    if owner and repo_name:
                         message = raw_commit_data.get('commit_message')
                         issue_numbers = extract_issue_ids(message)
                         if issue_numbers:
                             linked_ids = _process_and_link_commit_issues(
                                 session, repository_id, existing_id, owner, repo_name, issue_numbers, fetcher
                             )
                             commit_to_linked_issues_map[existing_id] = linked_ids
                    continue # Skip inserting the metric again

                # --- Create and Insert New CommitGuruMetric ---
                # Prepare data, excluding fields handled by relationships or calculated later
                metric_instance_data = {
                    "repository_id": repository_id, "commit_hash": commit_hash,
                    "parent_hashes": raw_commit_data.get('parent_hashes'),
                    "author_name": raw_commit_data.get('author_name'),
                    "author_email": raw_commit_data.get('author_email'),
                    "author_date": raw_commit_data.get('author_date'),
                    "author_date_unix_timestamp": raw_commit_data.get('author_date_unix_timestamp'),
                    "commit_message": raw_commit_data.get('commit_message'),
                    "is_buggy": False, # Will be updated after bug linking
                    "fix": raw_commit_data.get('fix'), # From keyword check
                    "fixing_commit_hashes": None, # Will be updated after bug linking
                    "files_changed": raw_commit_data.get('files_changed'),
                    # Include raw Guru metrics
                    "ns": raw_commit_data.get('ns'), "nd": raw_commit_data.get('nd'),
                    "nf": raw_commit_data.get('nf'), "entropy": raw_commit_data.get('entropy'),
                    "la": raw_commit_data.get('la'), "ld": raw_commit_data.get('ld'),
                    "lt": raw_commit_data.get('lt'), "ndev": raw_commit_data.get('ndev'),
                    "age": raw_commit_data.get('age'), "nuc": raw_commit_data.get('nuc'),
                    "exp": raw_commit_data.get('exp'), "rexp": raw_commit_data.get('rexp'),
                    "sexp": raw_commit_data.get('sexp'),
                }
                try:
                    metric_instance = CommitGuruMetric(**metric_instance_data)
                    session.add(metric_instance)
                    session.flush() # Flush to get the new ID
                    new_id = metric_instance.id
                    commit_hash_to_id_map[commit_hash] = new_id # Store the new ID
                    inserted_count += 1

                    # --- Process & Link Issues for the NEWLY inserted metric ---
                    if owner and repo_name:
                        message = raw_commit_data.get('commit_message')
                        issue_numbers = extract_issue_ids(message)
                        if issue_numbers:
                            linked_ids = _process_and_link_commit_issues(
                                session, repository_id, new_id, owner, repo_name, issue_numbers, fetcher
                            )
                            commit_to_linked_issues_map[new_id] = linked_ids

                except Exception as e:
                    logger.error(f"Error creating/linking issues for CommitGuruMetric {commit_hash[:7]}: {e}", exc_info=True)
                    logger.debug(f"Data causing error: {metric_instance_data}")
                    session.rollback() # Rollback metric insert and issue links for this commit
                    # Continue to next commit? Or raise? Let's continue for robustness.

                # Update progress periodically
                if (processed_count) % 100 == 0:
                    progress = 40 + int(40 * (processed_count / total_commits_found))
                    update_task_state(task, 'STARTED', f'Saving Commit Guru metrics & issues ({processed_count}/{total_commits_found})...', progress)

            # Commit transaction after processing all commits in the batch
            session.commit()

        except Exception as outer_err:
             logger.error(f"Error during batch commit guru processing/saving: {outer_err}", exc_info=True)
             session.rollback()
             raise # Re-raise to fail the task if batch fails

    logger.info(f"Task {task.request.id}: Finished initial saving/issue linking. Inserted {inserted_count} new Commit Guru metric records.")

    # --- Phase: Link Bugs ---
    update_task_state(task, 'STARTED', 'Identifying bug links...', 85)
    logger.info(f"Task {task_id}: Identifying corrective commits and linking bugs...")
    bug_link_warning = None
    bug_introducing_commit_ids: Set[int] = set() # Store IDs of buggy commits
    fixing_commit_map_for_update: Dict[int, List[str]] = {} # buggy_commit_id -> [fixing_hash1, ...]

    try:
        # Prepare info for the linker: corrective_hash -> earliest_linked_issue_ts
        corrective_commits_info: Dict[str, Optional[int]] = {}
        with get_sync_db_session() as session: # New session for timestamp queries
             for commit_hash, commit_id in commit_hash_to_id_map.items():
                 if commit_id != -1 and commit_fix_keyword_map.get(commit_hash, False):
                     # Query for the earliest timestamp for this corrective commit
                     earliest_ts = _get_earliest_linked_issue_timestamp(session, commit_id)
                     corrective_commits_info[commit_hash] = earliest_ts

        logger.info(f"Task {task_id}: Found {len(corrective_commits_info)} potential corrective commits for linking.")

        bug_link_map_hash: Dict[str, List[str]] = {} # buggy_hash -> [fixing_hash1,...]
        if corrective_commits_info:
            linker = GitCommitLinker(repo_local_path)
            bug_link_map_hash = linker.link_corrective_commits(corrective_commits_info)
            logger.info(f"Task {task_id}: Bug linking identified {len(bug_link_map_hash)} potential bug-introducing commits (by hash).")

            # Convert buggy hashes to buggy IDs for DB update
            for buggy_hash, fixing_hashes in bug_link_map_hash.items():
                buggy_id = commit_hash_to_id_map.get(buggy_hash, -1)
                if buggy_id != -1:
                    bug_introducing_commit_ids.add(buggy_id)
                    fixing_commit_map_for_update[buggy_id] = fixing_hashes
        else:
            logger.info(f"Task {task_id}: No corrective commits found or processed, skipping bug linking.")

        # --- Update is_buggy flag and fixing_commit_hashes in DB ---
        if bug_introducing_commit_ids:
            logger.info(f"Task {task_id}: Updating {len(bug_introducing_commit_ids)} commits identified as bug-introducing...")
            with get_sync_db_session() as session:
                try:
                    # Bulk update 'is_buggy'
                    update_buggy_stmt = (
                        update(CommitGuruMetric)
                        .where(CommitGuruMetric.id.in_(bug_introducing_commit_ids))
                        .values(is_buggy=True)
                    )
                    session.execute(update_buggy_stmt)

                    # Update fixing_commit_hashes individually (easier than complex bulk update)
                    for buggy_id, fixing_hashes in fixing_commit_map_for_update.items():
                         update_fixing_stmt = (
                             update(CommitGuruMetric)
                             .where(CommitGuruMetric.id == buggy_id)
                             .values(fixing_commit_hashes={"hashes": fixing_hashes})
                         )
                         session.execute(update_fixing_stmt)

                    session.commit()
                    logger.info(f"Task {task_id}: Successfully updated bug flags and fixing hashes.")
                except Exception as update_err:
                     logger.error(f"Task {task_id}: Failed during DB update for bug linking: {update_err}", exc_info=True)
                     session.rollback()
                     bug_link_warning = "Failed to update bug link flags in DB."

    except Exception as e:
        logger.error(f"Task {task_id}: Failed during bug linking phase: {e}", exc_info=True)
        bug_link_warning = 'Bug linking process failed.'
        # Allow task to continue, but report warning

    if bug_link_warning:
        update_task_state(task, 'STARTED', bug_link_warning, 88, warning=bug_link_warning)


    # Return inserted count, RAW data list (for CK), and any warning
    return inserted_count, commit_guru_raw_data_list, bug_link_warning

def run_ck_analysis(
    task: Task,
    repository_id: int,
    repo: Repo,
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
    except (GitCommandError, ValueError, IndexError, AttributeError, Exception) as e:
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

    with get_sync_db_session() as session:
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