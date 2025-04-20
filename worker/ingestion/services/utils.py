# worker/ingestion/services/utils.py
import logging
import os
import math
import tempfile
import subprocess
import dateutil.parser
from pathlib import Path
from typing import Any, Optional, Dict, List, Tuple
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import select, update, func

from shared.core.config import settings
from shared.utils.github_utils import GitHubIssueFetcher, GitHubAPIResponse, extract_issue_ids
from shared.db.models import GitHubIssue
from shared.db.models.commit_github_issue_association import commit_github_issue_association_table

logger = logging.getLogger(__name__)
# Set level from settings if available, otherwise default
log_level = getattr(settings, 'LOG_LEVEL', 'INFO')
logger.setLevel(log_level.upper())

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
            # logger.info(f"Using temporary directory for CK run: {temp_dir_path}") # Too verbose

            # --- Construct the FILE PREFIX for CK ---
            output_file_prefix = temp_dir_path / f"ck_output_{commit_hash}_"
            # logger.info(f"Passing output prefix to CK: {output_file_prefix}") # Too verbose

            # --- Expected output file paths based on the prefix ---
            expected_class_csv_path = Path(f"{output_file_prefix}class.csv")
            expected_method_csv_path = Path(f"{output_file_prefix}method.csv") # And others if needed

            # --- Run CK with the output file prefix ---
            try:
                # logger.info(f"Running CK for commit {commit_hash} on {repo_dir}...") # Too verbose
                command = [
                    'java', '-jar', str(CK_JAR_PATH), str(repo_dir),
                    use_jars, str(max_files_per_partition), variables_and_fields,
                    str(output_file_prefix) # <<< PASS THE PREFIX HERE
                ]
                # logger.debug(f"Executing command: {' '.join(command)}")

                completed_process = subprocess.run(
                    command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1200
                )
                # logger.debug(f"CK stdout for {commit_hash}:\n{completed_process.stdout.decode()}")
                if completed_process.stderr:
                     # Log stderr but don't necessarily treat log4j warnings as errors
                     stderr_output = completed_process.stderr.decode()
                     if "Exception" in stderr_output or "Error" in stderr_output: # Look for actual errors
                         logger.error(f"CK stderr reported errors for {commit_hash}:\n{stderr_output}")
                     else:
                          # Reduce noise from log4j warnings
                          if "log4j" not in stderr_output.lower():
                              logger.warning(f"CK stderr for {commit_hash}:\n{stderr_output}")

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
                # logger.info(f"Found expected CK output file: {expected_class_csv_path}") # Too verbose
                try:
                    metrics_df = pd.read_csv(expected_class_csv_path)
                    # logger.info(f"Successfully read {len(metrics_df)} CK metrics for {commit_hash}.") # Too verbose
                except pd.errors.EmptyDataError:
                     logger.warning(f"CK output file {expected_class_csv_path} is empty for {commit_hash}.")
                     metrics_df = pd.DataFrame()
                except Exception as e:
                     logger.error(f"Error reading CK output CSV {expected_class_csv_path} for {commit_hash}: {e}")
                     metrics_df = pd.DataFrame()
                finally:
                    # Clean up the specific output files manually
                    try:
                        if expected_class_csv_path.exists(): os.remove(expected_class_csv_path)
                        if expected_method_csv_path.exists(): os.remove(expected_method_csv_path)
                    except OSError as rm_err:
                         logger.error(f"Error removing CK output files like {expected_class_csv_path}: {rm_err}")
            else:
                logger.error(f"CK class output file NOT found at expected path: {expected_class_csv_path}")

        # --- Temporary directory is automatically cleaned up here ---
        # logger.debug(f"Temporary directory {temp_dir_name} and its contents automatically cleaned up.")

    except Exception as outer_e:
        logger.error(f"Error during temporary directory handling for {commit_hash}: {outer_e}", exc_info=True)
        return pd.DataFrame()

    return metrics_df


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
    from shared.db.models import CommitGuruMetric # Local import ok here

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
                # logger.debug(f"Issue #{issue_number} (DB ID: {issue_db_id}): ETag match (304). Updating last_fetched_at.")
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
                needs_linking = False
            else: # API Error
                logger.error(f"Issue #{issue_number}: API fetch failed for new issue (Status: {api_response.status_code}). Cannot link. Error: {api_response.error_message}")
                needs_linking = False

        # 4. Link Association (if issue DB ID is known and linking needed)
        if issue_db_id is not None and needs_linking:
            try:
                # ORM approach: Check existence first (less efficient but maybe simpler)
                link_exists_stmt = select(commit_github_issue_association_table).where(
                    commit_github_issue_association_table.c.commit_guru_metric_id == commit_metric_id,
                    commit_github_issue_association_table.c.github_issue_id == issue_db_id
                )
                link_exists = session.execute(link_exists_stmt).first() is not None

                if not link_exists:
                    # Get managed ORM objects if they are not already tracked
                    commit_metric_obj = session.get(CommitGuruMetric, commit_metric_id)
                    issue_obj = db_issue if db_issue else session.get(GitHubIssue, issue_db_id)

                    if commit_metric_obj and issue_obj:
                        # Append issue to the commit's relationship list
                        commit_metric_obj.github_issues.append(issue_obj)
                        session.add(commit_metric_obj) # Ensure change is tracked
                        linked_issue_db_ids.append(issue_db_id)
                        # logger.debug(f"Linked commit {commit_metric_id} to issue #{issue_number} (DB ID: {issue_db_id}) via ORM")
                    else:
                        logger.error(f"Failed to get ORM objects for linking commit {commit_metric_id} and issue {issue_db_id}")
                # else: logger.debug(f"Link already exists between commit {commit_metric_id} and issue {issue_db_id}")

            except Exception as link_err:
                 logger.error(f"Failed to link commit {commit_metric_id} to issue DB ID {issue_db_id}: {link_err}", exc_info=True)
                 # Rollback for this specific issue link attempt might be complex,
                 # better to handle rollback at the end of the commit processing.

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