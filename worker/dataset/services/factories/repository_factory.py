# worker/dataset/services/factories/repository_factory.py
import logging
from typing import Callable

# Import interfaces and concrete implementations
from services.interfaces import IRepositoryFactory
from sqlalchemy.orm import Session

from shared.core.config import settings
from shared.repositories import (
    BotPatternRepository,
    CKMetricRepository,
    CommitGuruMetricRepository,
    DatasetRepository,
    GitHubIssueRepository,
    RepositoryRepository,
)

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


class RepositoryFactory(IRepositoryFactory):
    """Provides instances of database repositories for the dataset worker."""

    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory
        # Cache repository instances per factory instance
        self._guru_repo: CommitGuruMetricRepository | None = None
        self._ck_repo: CKMetricRepository | None = None
        self._issue_repo: GitHubIssueRepository | None = None  # Not needed?
        self._dataset_repo: DatasetRepository | None = None
        self._repository_repo: RepositoryRepository | None = None
        self._bot_pattern_repo: BotPatternRepository | None = None
        logger.debug("Dataset Worker RepositoryFactory initialized.")

    def get_commit_guru_repo(self) -> CommitGuruMetricRepository:
        if self._guru_repo is None:
            self._guru_repo = CommitGuruMetricRepository(self.session_factory)
        return self._guru_repo

    def get_ck_metric_repo(self) -> CKMetricRepository:
        if self._ck_repo is None:
            self._ck_repo = CKMetricRepository(self.session_factory)
        return self._ck_repo

    def get_github_issue_repo(self) -> GitHubIssueRepository:
        # This likely isn't needed by the dataset worker, but implement if required
        if self._issue_repo is None:
            self._issue_repo = GitHubIssueRepository(self.session_factory)
        return self._issue_repo

    def get_dataset_repo(self) -> DatasetRepository:
        if self._dataset_repo is None:
            self._dataset_repo = DatasetRepository(self.session_factory)
        return self._dataset_repo

    def get_repository_repo(self) -> RepositoryRepository:
        if self._repository_repo is None:
            self._repository_repo = RepositoryRepository(self.session_factory)
        return self._repository_repo

    def get_bot_pattern_repo(self) -> BotPatternRepository:
        if self._bot_pattern_repo is None:
            self._bot_pattern_repo = BotPatternRepository(self.session_factory)
        return self._bot_pattern_repo
