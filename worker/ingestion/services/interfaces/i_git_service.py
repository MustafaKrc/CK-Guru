from abc import ABC, abstractmethod
from typing import Optional


class IGitService(ABC):
    """Interface defining Git command operations for a repository."""

    @abstractmethod
    def run_git_command(self, cmd_args: str, check: bool = True, suppress_stderr: bool = False) -> str:
        """Runs a git command."""
        pass

    @abstractmethod
    def resolve_ref_to_hash(self, ref: str) -> str:
        """Resolves a Git reference to its full commit hash."""
        pass

    @abstractmethod
    def get_first_parent_hash(self, commit_hash: str) -> Optional[str]:
        """Gets the full hash of the first parent of a commit."""
        pass

    @abstractmethod
    def does_commit_exist(self, commit_hash: str) -> bool:
        """Checks if a commit object exists locally."""
        pass

    @abstractmethod
    def clone_or_fetch(self, git_url: str) -> None:
        """Clones or fetches updates for the repository."""
        pass

    @abstractmethod
    def checkout_commit(self, commit_hash: str, force: bool = True) -> bool:
        """Checks out the repository at the specified commit."""
        pass

    @abstractmethod
    def determine_default_branch(self) -> str:
        """Determines the default branch name."""
        pass