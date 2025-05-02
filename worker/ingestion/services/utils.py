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
from shared.utils.github_utils import GitHubClient, GitHubAPIResponse, extract_issue_ids
from shared.db.models import GitHubIssue
from shared.db.models.commit_github_issue_association import commit_github_issue_association_table

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


# not used, but kept for potential future use
def _process_and_link_commit_issues(
    session: Session,
    repository_id: int,
    commit_metric_id: int, # The DB ID of the CommitGuruMetric record
    owner: str,
    repo_name: str,
    issue_numbers: List[str], # List of numbers like ['123', '45']
    fetcher: GitHubClient
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


