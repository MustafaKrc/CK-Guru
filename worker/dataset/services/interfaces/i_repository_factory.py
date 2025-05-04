# worker/dataset/services/interfaces/i_repository_factory.py
from abc import ABC, abstractmethod

from shared.repositories import (
    CKMetricRepository,
    CommitGuruMetricRepository,
    GitHubIssueRepository,
    DatasetRepository,        
    RepositoryRepository,     
    BotPatternRepository      
)

class IRepositoryFactory(ABC):
    """Interface for providing instances of database repositories."""

    @abstractmethod
    def get_commit_guru_repo(self) -> CommitGuruMetricRepository:
        pass

    @abstractmethod
    def get_ck_metric_repo(self) -> CKMetricRepository:
        pass

    @abstractmethod
    def get_github_issue_repo(self) -> GitHubIssueRepository:
        pass

    @abstractmethod
    def get_dataset_repo(self) -> DatasetRepository:
        pass

    @abstractmethod
    def get_repository_repo(self) -> RepositoryRepository:
        pass

    @abstractmethod
    def get_bot_pattern_repo(self) -> BotPatternRepository:
        pass