from abc import ABC, abstractmethod
from typing import Optional

from shared.schemas.repo_api_client import RepoApiClientResponse


class IRepositoryApiClient(ABC):
    """Interface for fetching data from the GitHub API."""

    @abstractmethod
    def get_issue(self, owner: str, repo_name: str, issue_number: str, current_etag: Optional[str] = None) -> RepoApiClientResponse:
        """Fetches data for a specific issue."""
        pass

    @staticmethod
    @abstractmethod
    def extract_repo_owner_name(git_url: str) -> Optional[tuple[str, str]]:
        """Extracts owner and repo name from a GitHub URL."""
        pass

    @staticmethod
    @abstractmethod
    def extract_issue_ids(commit_message: str) -> list[str]:
        """Extracts issue IDs from a commit message."""
        pass