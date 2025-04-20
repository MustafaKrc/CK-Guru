# worker/ingestion/services/steps/persist_guru_and_link_issues.py
import logging
from typing import Dict, List, Optional, Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .base import IngestionStep, IngestionContext
from shared.db_session import get_sync_db_session
from shared.db.models import CommitGuruMetric, GitHubIssue # Add GitHubIssue model
from shared.utils.github_utils import extract_repo_owner_name, GitHubIssueFetcher, extract_issue_ids
from shared.core.config import settings
# Import the helper function from utils.py
from ..utils import _process_and_link_commit_issues

logger = logging.getLogger(__name__)
log_level = getattr(settings, 'LOG_LEVEL', 'INFO')
logger.setLevel(log_level.upper())

class PersistCommitGuruAndLinkIssuesStep(IngestionStep):
    name = "Persist Guru Metrics & Link Issues"

    def execute(self, context: IngestionContext) -> IngestionContext:
        if not context.raw_commit_guru_data:
             self._log_info(context, "No raw Commit Guru data to persist.")
             return context

        owner, repo_name = None, None
        repo_info = extract_repo_owner_name(context.git_url)
        if repo_info:
            owner, repo_name = repo_info
            self._log_info(context, f"Extracted owner='{owner}', repo='{repo_name}' for issue linking.")
        else:
             self._log_warning(context, f"Could not extract owner/repo from {context.git_url}. Skipping GitHub issue linking.")

        fetcher = GitHubIssueFetcher(token=settings.GITHUB_TOKEN)
        inserted_count = 0
        processed_count = 0
        total_commits = len(context.raw_commit_guru_data)
        commit_to_linked_issues_map: Dict[int, List[int]] = {} # Store intermediate links if needed

        self._log_info(context, f"Persisting {total_commits} Commit Guru metrics and linking issues...")
        self._update_progress(context, f'Starting persistence/linking for {total_commits} commits...', 0)

        with get_sync_db_session() as session:
            try:
                for i, raw_commit_data in enumerate(context.raw_commit_guru_data):
                    processed_count += 1
                    commit_hash = raw_commit_data.get('commit_hash')
                    if not commit_hash:
                        self._log_warning(context, f"Skipping raw commit data entry {i+1} due to missing hash.")
                        continue

                    # Check existence using map populated in previous step
                    # Note: This check assumes the map is accurate and no concurrent runs are happening
                    # A DB check might be safer but slower.
                    existing_id = context.commit_hash_to_db_id_map.get(commit_hash)

                    current_commit_db_id = -1
                    if existing_id is not None and existing_id != -1:
                        # Already processed in a previous run (or maybe earlier in this run if map populated differently)
                        current_commit_db_id = existing_id
                        # Still need to link issues if not done before?
                        # Let's assume if ID exists, issues were linked previously.
                        # self._log_debug(context, f"Commit {commit_hash[:7]} already exists with ID {existing_id}. Skipping insert.")
                        pass # Skip insert
                    elif existing_id == -1: # Placeholder, means it needs insertion
                        # Create and Insert New CommitGuruMetric
                        metric_instance_data = {
                            "repository_id": context.repository_id, "commit_hash": commit_hash,
                            "parent_hashes": raw_commit_data.get('parent_hashes'),
                            "author_name": raw_commit_data.get('author_name'),
                            "author_email": raw_commit_data.get('author_email'),
                            "author_date": raw_commit_data.get('author_date'),
                            "author_date_unix_timestamp": raw_commit_data.get('author_date_unix_timestamp'),
                            "commit_message": raw_commit_data.get('commit_message'),
                            "is_buggy": False, # Will be updated after bug linking
                            "fix": context.commit_fix_keyword_map.get(commit_hash, False), # Use map value
                            "fixing_commit_hashes": None, # Will be updated after bug linking
                            "files_changed": raw_commit_data.get('files_changed'),
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
                            context.commit_hash_to_db_id_map[commit_hash] = new_id # Update map with real ID
                            current_commit_db_id = new_id
                            inserted_count += 1
                        except Exception as insert_err:
                             self._log_error(context, f"Failed to insert CommitGuruMetric for {commit_hash[:7]}: {insert_err}", exc_info=False)
                             session.rollback() # Rollback insert attempt for this commit
                             continue # Skip issue linking for this failed insert

                    # Process & Link Issues if owner/repo known and commit has a valid DB ID
                    if owner and repo_name and current_commit_db_id != -1:
                        message = raw_commit_data.get('commit_message')
                        issue_numbers = extract_issue_ids(message)
                        if issue_numbers:
                             try:
                                 linked_ids = _process_and_link_commit_issues(
                                     session, context.repository_id, current_commit_db_id,
                                     owner, repo_name, issue_numbers, fetcher
                                 )
                                 # Store linked IDs if needed later (e.g., bug linking)
                                 # commit_to_linked_issues_map[current_commit_db_id] = linked_ids
                             except Exception as link_err:
                                 self._log_error(context, f"Error linking issues for commit DB ID {current_commit_db_id}: {link_err}", exc_info=False)
                                 # Don't rollback the whole batch, just log error for this commit's issues


                    # Update progress periodically
                    if total_commits > 0 and processed_count % 100 == 0:
                        # Allocate, say, 40% of total task time for this step (adjust as needed)
                        step_progress = int(40 * (processed_count / total_commits))
                        self._update_progress(context, f'Persisting/Linking ({processed_count}/{total_commits})...', step_progress)

                session.commit() # Commit transaction after processing all commits

            except SQLAlchemyError as db_err:
                self._log_error(context, f"Database error during persistence/linking: {db_err}")
                session.rollback()
                raise # Re-raise critical DB error
            except Exception as e:
                self._log_error(context, f"Unexpected error during persistence/linking: {e}", exc_info=True)
                session.rollback()
                raise # Re-raise other critical errors

        context.inserted_guru_metrics_count = inserted_count
        self._log_info(context, f"Persisted {inserted_count} new Commit Guru metrics and linked issues.")
        # Update progress after step completion
        self._update_progress(context, f'Finished persistence/linking.', 40) # Example progress value
        return context