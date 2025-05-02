# worker/ingestion/services/steps/persist_guru_and_link_issues.py
from datetime import datetime, timezone
import logging
import dateutil.parser # Add this import
from typing import Dict, List, Optional, Any

from sqlalchemy import select, update # Keep select/update for issues
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
# Import PostgreSQL specific insert for UPSERT
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .base import IngestionStep, IngestionContext
from shared.db_session import get_sync_db_session
# Import models
from shared.db.models import CommitGuruMetric, GitHubIssue
# Import GitHub Client and helpers
from shared.utils.github_utils import GitHubClient, extract_repo_owner_name, extract_issue_ids, GitHubAPIResponse
from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

# Helper Function for Issue Processing (extracted for clarity)
def _fetch_or_create_linked_issue(
    session: Session,
    fetcher: GitHubClient,
    repository_id: int,
    owner: str,
    repo_name: str,
    issue_number: int
) -> Optional[GitHubIssue]:
    """
    Fetches an issue from GitHub API using ETag caching, updates or creates
    the record in the database. Returns the managed GitHubIssue ORM object or None.
    """
    issue_db_id: Optional[int] = None
    db_issue: Optional[GitHubIssue] = None

    # 1. DB Lookup
    stmt = select(GitHubIssue).where(
        GitHubIssue.repository_id == repository_id,
        GitHubIssue.issue_number == issue_number
    )
    db_issue = session.execute(stmt).scalar_one_or_none()
    current_etag = db_issue.etag if db_issue else None

    # 2. Conditional API Fetch
    api_response: GitHubAPIResponse = fetcher.get_issue(
        owner, repo_name, str(issue_number), current_etag=current_etag
    )

    # 3. Handle API Response and DB Update/Insert
    now_utc = datetime.now(timezone.utc)
    if db_issue:
        # --- Issue Found in DB ---
        if api_response.status_code == 304: # Not Modified
            db_issue.last_fetched_at = now_utc # Update timestamp
            session.add(db_issue)
        elif api_response.status_code == 200 and api_response.json_data: # Modified
            new_data = api_response.json_data
            db_issue.state = new_data.get('state', db_issue.state) # Keep old state if missing
            db_issue.github_id = new_data.get('id', db_issue.github_id)
            db_issue.api_url = new_data.get('url', db_issue.api_url)
            db_issue.html_url = new_data.get('html_url', db_issue.html_url)
            created_at_str = new_data.get('created_at')
            closed_at_str = new_data.get('closed_at')
            try: db_issue.created_at_timestamp = int(dateutil.parser.isoparse(created_at_str).timestamp()) if created_at_str else db_issue.created_at_timestamp
            except (TypeError, ValueError): pass # Keep old value on parse error
            try: db_issue.closed_at_timestamp = int(dateutil.parser.isoparse(closed_at_str).timestamp()) if closed_at_str else db_issue.closed_at_timestamp
            except (TypeError, ValueError): pass # Keep old value on parse error
            db_issue.etag = api_response.etag
            db_issue.last_fetched_at = now_utc
            session.add(db_issue)
        elif api_response.status_code in [404, 410]: # Gone / Deleted
            logger.warning(f"Issue #{issue_number} (DB ID: {db_issue.id}): Now missing on GitHub ({api_response.status_code}). Marking as deleted.")
            db_issue.state = 'deleted'; db_issue.etag = None; db_issue.last_fetched_at = now_utc
            session.add(db_issue)
        else: # API Error - Use stale data, don't update ETag/timestamps
            logger.error(f"Issue #{issue_number} (DB ID: {db_issue.id}): API fetch failed ({api_response.status_code}). Using stale data. Error: {api_response.error_message}")
        return db_issue # Return existing (potentially updated) DB object

    else:
        # --- Issue NOT Found in DB ---
        if api_response.status_code == 200 and api_response.json_data:
            logger.info(f"Issue #{issue_number}: Found on GitHub. Inserting into DB.")
            new_data = api_response.json_data
            created_at, closed_at = None, None
            created_at_str = new_data.get('created_at')
            closed_at_str = new_data.get('closed_at')
            try: created_at = int(dateutil.parser.isoparse(created_at_str).timestamp()) if created_at_str else None
            except (TypeError, ValueError): pass
            try: closed_at = int(dateutil.parser.isoparse(closed_at_str).timestamp()) if closed_at_str else None
            except (TypeError, ValueError): pass

            new_issue = GitHubIssue(
                repository_id=repository_id, issue_number=issue_number,
                github_id=new_data.get('id'), state=new_data.get('state', 'unknown'),
                created_at_timestamp=created_at, closed_at_timestamp=closed_at,
                api_url=new_data.get('url'), html_url=new_data.get('html_url'),
                last_fetched_at=now_utc, etag=api_response.etag
            )
            session.add(new_issue)
            # We need the ID for linking, so flush is necessary here
            # Flushing within the loop can impact performance vs bulk insert + later query,
            # but simplifies getting the ID immediately for linking.
            try:
                session.flush([new_issue]) # Flush only this object to get ID
                logger.debug(f"Flushed new GitHubIssue #{issue_number}, got DB ID: {new_issue.id}")
                return new_issue # Return the new ORM object
            except Exception as flush_err:
                 logger.error(f"Failed to flush new GitHubIssue #{issue_number}: {flush_err}", exc_info=True)
                 session.rollback() # Rollback the failed flush
                 return None # Indicate failure to create/get ID

        elif api_response.status_code in [404, 410]:
            logger.warning(f"Issue #{issue_number}: Not found on GitHub ({api_response.status_code}). Skipping linking.")
            return None
        else: # API Error
            logger.error(f"Issue #{issue_number}: API fetch failed for new issue ({api_response.status_code}). Cannot link. Error: {api_response.error_message}")
            return None

class PersistCommitGuruAndLinkIssuesStep(IngestionStep):
    name = "Persist Guru Metrics & Link Issues"

    def execute(self, context: IngestionContext) -> IngestionContext:
        if not context.raw_commit_guru_data:
             self._log_info(context, "No raw Commit Guru data to persist.")
             return context

        owner, repo_name = None, None
        repo_info = extract_repo_owner_name(context.git_url)
        can_link_issues = False
        if repo_info:
            owner, repo_name = repo_info
            can_link_issues = True
            self._log_info(context, f"Extracted owner='{owner}', repo='{repo_name}' for issue linking.")
        else:
             self._log_warning(context, f"Could not extract owner/repo from {context.git_url}. Skipping GitHub issue linking.")

        # Instantiate GitHubClient only if needed
        fetcher = GitHubClient(token=settings.GITHUB_TOKEN) if can_link_issues else None

        commits_to_upsert: List[Dict[str, Any]] = []
        # Store data needed for issue linking after upsert: {commit_hash: [issue_numbers]}
        commit_hash_to_issue_numbers: Dict[str, List[str]] = {}

        total_commits = len(context.raw_commit_guru_data)
        processed_count = 0

        self._log_info(context, f"Preparing {total_commits} Commit Guru metrics for persistence/linking...")
        self._update_progress(context, f'Preparing {total_commits} commits...', 0)

        # 1. Prepare data for bulk upsert and collect issue numbers
        for i, raw_commit_data in enumerate(context.raw_commit_guru_data):
            processed_count += 1
            commit_hash = raw_commit_data.get('commit_hash')
            if not commit_hash:
                self._log_warning(context, f"Skipping raw commit data entry {i+1} due to missing hash.")
                continue

            # Prepare data dict for upsert
            metric_data = {
                "repository_id": context.repository_id, "commit_hash": commit_hash,
                "parent_hashes": raw_commit_data.get('parent_hashes'),
                "author_name": raw_commit_data.get('author_name'),
                "author_email": raw_commit_data.get('author_email'),
                "author_date": raw_commit_data.get('author_date'),
                "author_date_unix_timestamp": raw_commit_data.get('author_date_unix_timestamp'),
                "commit_message": raw_commit_data.get('commit_message'),
                "is_buggy": False, # Default, updated later by LinkBugsStep
                "fix": context.commit_fix_keyword_map.get(commit_hash, False),
                "fixing_commit_hashes": None, # Default, updated later by LinkBugsStep
                "files_changed": raw_commit_data.get('files_changed'),
                "ns": raw_commit_data.get('ns'), "nd": raw_commit_data.get('nd'),
                "nf": raw_commit_data.get('nf'), "entropy": raw_commit_data.get('entropy'),
                "la": raw_commit_data.get('la'), "ld": raw_commit_data.get('ld'),
                "lt": raw_commit_data.get('lt'), "ndev": raw_commit_data.get('ndev'),
                "age": raw_commit_data.get('age'), "nuc": raw_commit_data.get('nuc'),
                "exp": raw_commit_data.get('exp'), "rexp": raw_commit_data.get('rexp'),
                "sexp": raw_commit_data.get('sexp'),
            }
            commits_to_upsert.append(metric_data)

            # Extract issue numbers if linking is possible
            if can_link_issues:
                message = raw_commit_data.get('commit_message')
                issue_numbers = extract_issue_ids(message)
                if issue_numbers:
                    commit_hash_to_issue_numbers[commit_hash] = issue_numbers

            if total_commits > 0 and processed_count % 100 == 0:
                step_progress = int(50 * (processed_count / total_commits)) # Allocate 50% for prep/upsert
                self._update_progress(context, f'Preparing ({processed_count}/{total_commits})...', step_progress)

        # 2. Perform Bulk Upsert and Get IDs
        db_ids_map: Dict[str, int] = {} # {commit_hash: db_id}
        if commits_to_upsert:
            self._log_info(context, f"Performing bulk UPSERT for {len(commits_to_upsert)} CommitGuruMetrics...")
            with get_sync_db_session() as session:
                try:
                    index_elements = ['repository_id', 'commit_hash'] # Unique constraint
                    stmt = pg_insert(CommitGuruMetric).values(commits_to_upsert)
                    update_columns = { # Update all columns except the constraint keys on conflict
                        col.name: col for col in stmt.excluded
                        if col.name not in index_elements
                    }
                    # Add RETURNING id to get the IDs of inserted/updated rows
                    upsert_stmt = stmt.on_conflict_do_update(
                        index_elements=index_elements, set_=update_columns
                    ).returning(CommitGuruMetric.id, CommitGuruMetric.commit_hash)

                    # Execute and fetch results
                    upsert_results = session.execute(upsert_stmt).fetchall()
                    session.commit() # Commit the upsert

                    # Populate the map with actual DB IDs
                    for row_id, row_hash in upsert_results:
                        db_ids_map[row_hash] = row_id

                    self._log_info(context, f"Bulk UPSERT executed. Processed {len(upsert_results)} rows.")
                    # Update context map - important for LinkBugsStep
                    context.commit_hash_to_db_id_map.update(db_ids_map)
                    context.inserted_guru_metrics_count = len(db_ids_map) # Count successful upserts

                except SQLAlchemyError as db_err:
                    self._log_error(context, f"Database error during CommitGuruMetric UPSERT: {db_err}", exc_info=True)
                    session.rollback()
                    raise # Re-raise critical DB error
                except Exception as e:
                    self._log_error(context, f"Unexpected error during CommitGuruMetric UPSERT: {e}", exc_info=True)
                    session.rollback()
                    raise

        # 3. Link Issues (if possible and needed)
        if can_link_issues and fetcher and commit_hash_to_issue_numbers and db_ids_map:
            self._log_info(context, f"Linking issues for {len(commit_hash_to_issue_numbers)} commits...")
            self._update_progress(context, "Linking GitHub issues...", 50) # Start linking progress
            processed_link_count = 0
            total_links_to_process = len(commit_hash_to_issue_numbers)

            with get_sync_db_session() as session:
                try:
                    commit_orm_cache: Dict[int, CommitGuruMetric] = {} # Cache fetched commit objects

                    for commit_hash, issue_numbers in commit_hash_to_issue_numbers.items():
                        processed_link_count += 1
                        commit_db_id = db_ids_map.get(commit_hash)
                        if not commit_db_id:
                            self._log_warning(context, f"Skipping issue linking for {commit_hash[:7]}, DB ID not found after upsert.")
                            continue

                        # Get commit ORM object (cache lookup)
                        commit_metric_obj = commit_orm_cache.get(commit_db_id)
                        if not commit_metric_obj:
                            commit_metric_obj = session.get(CommitGuruMetric, commit_db_id)
                            if commit_metric_obj: commit_orm_cache[commit_db_id] = commit_metric_obj
                            else:
                                 self._log_error(context, f"Failed to retrieve CommitGuruMetric {commit_db_id} for issue linking.")
                                 continue

                        linked_issue_count_for_commit = 0
                        for number_str in issue_numbers:
                            try: issue_number = int(number_str)
                            except ValueError: continue

                            # Fetch/Create issue ORM object
                            issue_obj = _fetch_or_create_linked_issue(
                                session, fetcher, context.repository_id, owner, repo_name, issue_number
                            )

                            # Link using ORM relationship (handles association table)
                            if issue_obj and issue_obj not in commit_metric_obj.github_issues:
                                commit_metric_obj.github_issues.append(issue_obj)
                                session.add(commit_metric_obj) # Ensure change is tracked
                                linked_issue_count_for_commit += 1

                        if linked_issue_count_for_commit > 0:
                             self._log_debug(context, f"Linked {linked_issue_count_for_commit} issues to commit {commit_hash[:7]} (ID: {commit_db_id}).")

                        if total_links_to_process > 0 and processed_link_count % 50 == 0:
                             step_progress = 50 + int(50 * (processed_link_count / total_links_to_process))
                             self._update_progress(context, f'Linking issues ({processed_link_count}/{total_links_to_process})...', step_progress)


                    session.commit() # Commit all issue links
                    self._log_info(context, "Finished linking GitHub issues.")
                except SQLAlchemyError as db_err:
                     self._log_error(context, f"Database error during issue linking: {db_err}", exc_info=True)
                     session.rollback()
                     # Don't fail the whole step, just log warning
                     self._log_warning(context, "Issue linking failed due to DB error.")
                except Exception as e:
                     self._log_error(context, f"Unexpected error during issue linking: {e}", exc_info=True)
                     session.rollback()
                     self._log_warning(context, "Issue linking failed due to unexpected error.")

        self._update_progress(context, "Persistence & Linking step complete.", 100)
        return context