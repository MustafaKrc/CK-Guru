# worker/ingestion/services/factories/repository_factory.py
import logging
from typing import Callable

from sqlalchemy.orm import Session

from shared.core.config import settings
from shared.repositories.ck_metric_repository import CKMetricRepository
from shared.repositories.commit_guru_metric_repository import CommitGuruMetricRepository
from shared.repositories.github_issue_repository import GitHubIssueRepository
from shared.repositories.repository_repository import RepositoryRepository

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


class RepositoryFactory:
    """Provides instances of database repositories."""

    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory
        # Cache repository instances if they are stateless per factory instance
        self._guru_repo = None
        self._ck_repo = None
        self._issue_repo = None
        self._repo_repo = None

    def get_commit_guru_repo(self) -> CommitGuruMetricRepository:
        # logger.warning("Placeholder: get_commit_guru_repo() called - Returning None")
        if not self._guru_repo:
            self._guru_repo = CommitGuruMetricRepository(self.session_factory)
        return self._guru_repo

    def get_ck_metric_repo(self) -> CKMetricRepository:
        # logger.warning("Placeholder: get_ck_metric_repo() called - Returning None")
        if not self._ck_repo:
            self._ck_repo = CKMetricRepository(self.session_factory)
        return self._ck_repo

    def get_github_issue_repo(self) -> GitHubIssueRepository:
        # logger.warning("Placeholder: get_github_issue_repo() called - Returning None")
        if not self._issue_repo:
            self._issue_repo = GitHubIssueRepository(self.session_factory)
        return self._issue_repo

    def get_repository_repo(self) -> RepositoryRepository:
        # logger.warning("Placeholder: get_repository_repo() called - Returning None")
        if not self._repo_repo:
            self._repo_repo = RepositoryRepository(self.session_factory)
        return self._repo_repo

    # --- Unit of Work Methods ---
    # We preferred to not use UoW pattern for a single pipeline.
    # It is more useful when we save succeded steps.
    def start_unit_of_work(self):
        logger.debug("Placeholder: Starting Unit of Work.")
        # Potentially start a transaction or manage a shared session

    def commit_unit_of_work(self):
        logger.debug("Placeholder: Committing Unit of Work.")
        # Commit the shared session

    def rollback_unit_of_work(self):
        logger.debug("Placeholder: Rolling back Unit of Work.")
        # Rollback the shared session
