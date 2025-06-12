# shared/repositories/github_issue_repository.py
import logging
from datetime import datetime, timezone
from typing import Optional

import dateutil.parser
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from shared.db.models import GitHubIssue
from shared.schemas.repo_api_client import RepoApiClientResponse

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class GitHubIssueRepository(BaseRepository[GitHubIssue]):
    """Handles database operations for GitHubIssue."""

    def get_by_number(self, repo_id: int, issue_number: int) -> Optional[GitHubIssue]:
        """Gets a GitHubIssue by repository ID and issue number."""
        with self._session_scope() as session:
            stmt = select(GitHubIssue).where(
                GitHubIssue.repository_id == repo_id,
                GitHubIssue.issue_number == issue_number,
            )
            return session.execute(stmt).scalar_one_or_none()

    def update_or_create_from_api(
        self,
        repo_id: int,
        issue_number: int,
        api_response: RepoApiClientResponse,  # noqa: F821
    ) -> Optional[GitHubIssue]:
        """
        Updates or creates a GitHubIssue based on API response data.
        Handles 304 Not Modified, 200 OK, 404 Not Found, 410 Gone.

        Returns:
            The managed GitHubIssue object (updated or new) or None if the issue
            could not be found/created or an API error occurred.
        """
        with self._session_scope() as session:
            db_issue = self.get_by_number(
                repo_id, issue_number
            )  # Use own method for consistency
            now_utc = datetime.now(timezone.utc)
            managed_issue = None  # Store the final object to return

            if db_issue:
                # --- Issue Found in DB ---
                if api_response.status_code == 304:  # Not Modified
                    db_issue.last_fetched_at = now_utc
                    session.add(db_issue)
                    managed_issue = db_issue
                elif (
                    api_response.status_code == 200 and api_response.json_data
                ):  # Modified
                    new_data = api_response.json_data
                    db_issue.state = new_data.get("state", db_issue.state)
                    db_issue.github_id = new_data.get("id", db_issue.github_id)
                    db_issue.api_url = new_data.get("url", db_issue.api_url)
                    db_issue.html_url = new_data.get("html_url", db_issue.html_url)
                    created_at_str = new_data.get("created_at")
                    closed_at_str = new_data.get("closed_at")
                    try:
                        db_issue.created_at_timestamp = (
                            int(dateutil.parser.isoparse(created_at_str).timestamp())
                            if created_at_str
                            else db_issue.created_at_timestamp
                        )
                    except (TypeError, ValueError, AttributeError):
                        logger.warning(
                            f"Could not parse create date '{created_at_str}'"
                        )
                    try:
                        db_issue.closed_at_timestamp = (
                            int(dateutil.parser.isoparse(closed_at_str).timestamp())
                            if closed_at_str
                            else db_issue.closed_at_timestamp
                        )
                    except (TypeError, ValueError, AttributeError):
                        logger.warning(f"Could not parse close date '{closed_at_str}'")
                    db_issue.etag = api_response.etag
                    db_issue.last_fetched_at = now_utc
                    session.add(db_issue)
                    managed_issue = db_issue
                elif api_response.status_code in [404, 410]:  # Gone
                    db_issue.state = "deleted"
                    db_issue.etag = None
                    db_issue.last_fetched_at = now_utc
                    session.add(db_issue)
                    managed_issue = db_issue  # Return the 'deleted' record
                else:  # API Error
                    logger.error(
                        f"GitHubIssueRepository: API error {api_response.status_code} for existing issue #{issue_number}. Using stale data."
                    )
                    managed_issue = db_issue  # Return stale object

            else:
                # --- Issue NOT Found in DB ---
                if api_response.status_code == 200 and api_response.json_data:
                    new_data = api_response.json_data
                    created_at, closed_at = None, None
                    created_at_str = new_data.get("created_at")
                    closed_at_str = new_data.get("closed_at")
                    try:
                        created_at = (
                            int(dateutil.parser.isoparse(created_at_str).timestamp())
                            if created_at_str
                            else None
                        )
                    except (TypeError, ValueError, AttributeError):
                        logger.warning(
                            f"Could not parse create date '{created_at_str}'"
                        )
                    try:
                        closed_at = (
                            int(dateutil.parser.isoparse(closed_at_str).timestamp())
                            if closed_at_str
                            else None
                        )
                    except (TypeError, ValueError, AttributeError):
                        logger.warning(f"Could not parse close date '{closed_at_str}'")

                    new_issue = GitHubIssue(
                        repository_id=repo_id,
                        issue_number=issue_number,
                        github_id=new_data.get("id"),
                        state=new_data.get("state", "unknown"),
                        created_at_timestamp=created_at,
                        closed_at_timestamp=closed_at,
                        api_url=new_data.get("url"),
                        html_url=new_data.get("html_url"),
                        last_fetched_at=now_utc,
                        etag=api_response.etag,
                    )
                    session.add(new_issue)
                    managed_issue = new_issue  # Return the newly created object
                    # No flush needed here, let commit handle it
                elif api_response.status_code in [404, 410]:
                    logger.warning(
                        f"GitHubIssueRepository: Issue #{issue_number} not found on GitHub ({api_response.status_code}). Cannot create."
                    )
                    managed_issue = None
                else:  # API Error
                    logger.error(
                        f"GitHubIssueRepository: API error {api_response.status_code} for new issue #{issue_number}. Cannot create. Error: {api_response.error_message}"
                    )
                    managed_issue = None

            if managed_issue:
                try:
                    session.commit()  # Commit changes for this single issue
                    session.refresh(
                        managed_issue
                    )  # Ensure state is up-to-date after commit
                    return managed_issue
                except SQLAlchemyError as e:
                    logger.error(
                        f"GitHubIssueRepository: DB error updating/creating issue #{issue_number}: {e}",
                        exc_info=True,
                    )
                    session.rollback()
                    return None  # Return None on DB error
                except Exception as e:
                    logger.error(
                        f"GitHubIssueRepository: Unexpected error updating/creating issue #{issue_number}: {e}",
                        exc_info=True,
                    )
                    session.rollback()
                    return None
            else:
                # No commit needed if nothing was changed or created
                return None
