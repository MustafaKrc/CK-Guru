# worker/ingestion/services/git_service.py
from abc import ABC, abstractmethod
import logging
import shutil
import subprocess
from typing import Optional
from pathlib import Path
import git 

from services.interfaces.i_git_service import IGitService

# Import settings for logger configuration
from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

class GitCommandError(Exception):
    """Custom exception for Git command failures."""
    def __init__(self, message, stderr=None, returncode=None):
        super().__init__(message)
        self.stderr = stderr
        self.returncode = returncode

class GitRefNotFoundError(GitCommandError):
    """Specific exception for 'git rev-parse' failures."""
    pass

class GitService(IGitService):
    """Encapsulates Git command operations for a repository."""

    def __init__(self, repo_path: Path):
        """
        Initializes the GitService.

        Args:
            repo_path: The path to the local Git repository clone.
        """
        if not repo_path or not repo_path.is_dir():
            raise FileNotFoundError(f"Repository path does not exist or is not a directory: {repo_path}")
        self.repo_path = repo_path
        logger.debug(f"GitService initialized for path: {self.repo_path}")

    def clone_or_fetch(self, git_url: str) -> None:
        """
        Clones the repository if it doesn't exist locally, or fetches updates
        if it does. Ensures the repository at self.repo_path is ready.

        Args:
            git_url: The remote URL of the repository.

        Raises:
            GitCommandError: If cloning or fetching fails critically.
            FileNotFoundError: If the parent directory cannot be created.
        """
        if self.repo_path.exists():
            logger.info(f"Found existing clone at {self.repo_path}. Fetching updates...")
            try:
                # Get a Repo instance to use GitPython's fetch for convenience
                # (Could also use run_git_command('fetch ...'))
                repo = git.Repo(self.repo_path)
                # Ensure clean state before fetching
                repo.git.reset('--hard', '--quiet') # Add quiet
                repo.git.clean('-fdx', '--quiet')   # Add quiet
                origin = repo.remotes.origin
                origin.fetch(prune=True) # Prune deleted remote branches
                logger.info(f"Fetch complete for {self.repo_path}.")
                return # Success
            except (git.GitCommandError, Exception) as e:
                logger.warning(f"Error updating existing repo at {self.repo_path}. Re-cloning. Error: {e}")
                try:
                    shutil.rmtree(self.repo_path) # Clean up problematic clone
                except OSError as rm_err:
                    logger.error(f"Failed to remove existing clone directory {self.repo_path}: {rm_err}")
                    raise FileNotFoundError(f"Failed to clean up existing broken clone at {self.repo_path}") from rm_err
                # Fall through to clone if cleanup succeeded

        # Clone if it doesn't exist or update failed
        logger.info(f"Cloning {git_url} to {self.repo_path}...")
        try:
            # Ensure parent directory exists
            self.repo_path.parent.mkdir(parents=True, exist_ok=True)
            # Use GitPython's clone for potentially better credential handling etc.
            # no_checkout=True speeds up if we checkout specific commits later
            git.Repo.clone_from(git_url, self.repo_path, no_checkout=True)
            logger.info("Cloning complete.")
        except git.GitCommandError as e:
            logger.error(f"Failed to clone repository {git_url}: {e}", exc_info=True)
            raise GitCommandError(f"Failed to clone repository {git_url}: {e.stderr}", stderr=e.stderr, returncode=e.status) from e
        except Exception as e:
             logger.error(f"Unexpected error during clone of {git_url}: {e}", exc_info=True)
             raise GitCommandError(f"Unexpected error during clone: {e}") from e

    def run_git_command(self, cmd_args: str, check: bool = True, suppress_stderr: bool = False) -> str:
        """
        Helper to run git commands within the service's repository path.

        Args:
            cmd: The git command string (e.g., "status", "rev-list -n 1 HEAD").
                 'git ' prefix is added automatically.
            check: If True, raise CalledProcessError on non-zero exit code.

        Returns:
            The stdout of the command as a string.

        Raises:
            subprocess.CalledProcessError: If check is True and command fails.
            FileNotFoundError: If git executable is not found.
            Exception: For other unexpected errors.
        """
        full_cmd = f"git {cmd_args}"
        try:
            # logger.debug(f"Running command in {self.repo_path}: {full_cmd[:100]}...")
            result = subprocess.run(
                full_cmd, shell=True, cwd=self.repo_path, check=check, capture_output=True,
                text=True, encoding='utf-8', errors='ignore'
            )
            stderr_strip = result.stderr.strip() if result.stderr else ""
            if stderr_strip and not suppress_stderr:
                 # Log non-fatal stderr as warning
                 if result.returncode == 0 :
                      logger.warning(f"Git command stderr (Success): {stderr_strip}")
                 # Fatal stderr logged within CalledProcessError handling below
            return result.stdout
        except subprocess.CalledProcessError as e:
            stderr_output = e.stderr.strip() if e.stderr else "(no stderr)"
            error_message = (
                f"Git command failed (exit code {e.returncode}) in {self.repo_path}.\n"
                f"Command: {e.cmd}\nStderr: {stderr_output}"
            )
            logger.error(error_message)
            raise GitCommandError(error_message, stderr=stderr_output, returncode=e.returncode) from e
        except FileNotFoundError:
            msg = "Git command 'git' not found. Ensure git is installed and in PATH."
            logger.critical(msg)
            raise GitCommandError(msg) from None 
        except Exception as e:
            logger.error(f"Unexpected error running git command '{full_cmd[:100]}...' in {self.repo_path}: {e}", exc_info=True)
            raise GitCommandError(f"Unexpected error: {e}") from e

    def resolve_ref_to_hash(self, ref: str) -> str:
        """Resolves a Git reference (branch, tag, partial hash) to its full commit hash."""
        cmd_args = f"rev-parse --verify {ref}^{{commit}}" # Ensures it resolves to a commit object
        try:
            full_hash = self.run_git_command(cmd_args, check=True, suppress_stderr=True).strip()
            if not full_hash or len(full_hash) != 40:
                raise GitRefNotFoundError(f"Resolved ref '{ref}' resulted in invalid hash '{full_hash}'.")
            logger.debug(f"Resolved ref '{ref}' to {full_hash}")
            return full_hash
        except GitCommandError as e:
            # Intercept stderr specifically for rev-parse failures
            if e.stderr and ("unknown revision" in e.stderr.lower() or "bad revision" in e.stderr.lower()):
                 raise GitRefNotFoundError(f"Reference '{ref}' not found or invalid in repository {self.repo_path}.") from e
            raise # Re-raise other GitCommandErrors

    def get_first_parent_hash(self, commit_hash: str) -> Optional[str]:
        """Gets the full hash of the first parent of a commit, or None if it's the initial commit."""
        # Ensure the input hash is valid first
        if not self.does_commit_exist(commit_hash):
             logger.warning(f"Cannot get parent of non-existent commit: {commit_hash}")
             return None

        cmd_args = f"rev-parse --verify --quiet {commit_hash}^1" # Use ^1 for first parent, --quiet suppresses errors
        try:
            # Use check=False, empty output means no first parent
            parent_hash = self.run_git_command(cmd_args, check=False, suppress_stderr=True).strip()
            if parent_hash and len(parent_hash) == 40:
                logger.debug(f"Found parent {parent_hash} for commit {commit_hash}")
                return parent_hash
            else:
                logger.info(f"Commit {commit_hash} has no first parent (likely initial commit).")
                return None
        except GitCommandError as e:
            # Should be suppressed by --quiet, but log if error occurs anyway
            logger.error(f"Error getting parent for commit {commit_hash}: {e}", exc_info=True)
            return None

    def does_commit_exist(self, commit_hash: str) -> bool:
        """Checks if a commit object exists locally."""
        # 'git cat-file -e <hash>' exits 0 if exists, non-zero otherwise. Ignores output.
        # Alternatively, use rev-parse --verify
        cmd_args = f"cat-file -e {commit_hash}"
        try:
            # Use check=False, suppress stderr. Exit code determines existence.
            self.run_git_command(cmd_args, check=False, suppress_stderr=True)
            # If run_git_command didn't raise (even with check=False, assuming non-zero exit isn't an *error* here), it exists
            return True
        except GitCommandError as e:
             # Any error (including non-zero exit from cat-file) means it doesn't exist or invalid hash
             return False
        except Exception: # Catch other potential errors
             return False

    def find_commit_hash_before_timestamp(self, timestamp: int) -> Optional[str]:
        """
        Finds the hash of the latest commit made strictly *before* a given Unix timestamp.
        Uses the repository path associated with this service instance.

        Args:
            timestamp: The Unix timestamp (integer seconds since epoch).

        Returns:
            The commit hash (str) or None if no such commit exists or an error occurs.
        """
        cmd = f'rev-list -n 1 --before={timestamp} HEAD'
        try:
            # Use check=False as finding no commit is not necessarily a failure
            commit_hash = self.run_git_command(cmd, check=False).strip()
            if commit_hash and len(commit_hash) == 40: # Basic validation
                logger.debug(f"Found commit {commit_hash[:7]} before timestamp {timestamp} in {self.repo_path}")
                return commit_hash
            else:
                # This is expected if the timestamp is too early
                logger.info(f"No commit found before timestamp {timestamp} in {self.repo_path}")
                return None
        except Exception as e: # Catch errors from run_git_command or others
            logger.error(f"Error finding commit before timestamp {timestamp} in {self.repo_path}: {e}", exc_info=True)
            return None

    def checkout_commit(self, commit_hash: str, force: bool = True) -> bool:
        """Checks out the repository at the specified commit using the service's repo path."""
        # Using GitPython here might be cleaner if self.repo = git.Repo() is initialized
        # If using Repo object:
        # try:
        #     repo = git.Repo(self.repo_path) # Get Repo instance
        #     logger.debug(f"Checking out commit {commit_hash} in {self.repo_path}...")
        #     repo.git.reset('--hard')
        #     repo.git.clean('-fdx')
        #     repo.git.checkout(commit_hash, force=force)
        #     logger.debug(f"Checkout successful for {commit_hash}.")
        #     return True
        # except git.GitCommandError as e:
        #      logger.error(f"Error checking out commit {commit_hash}: {e.stderr}")
        #      return False
        # except Exception as e:
        #      logger.error(f"Unexpected error during checkout of {commit_hash}: {e}", exc_info=True)
        #      return False

        # Alternative using subprocess:
        try:
            logger.debug(f"Checking out commit {commit_hash} in {self.repo_path}...")
            # Clean state first
            self.run_git_command('reset --hard', check=True)
            self.run_git_command('clean -fdx', check=True)
            checkout_cmd = f'checkout {"--force " if force else ""}{commit_hash}'
            self.run_git_command(checkout_cmd, check=True)
            logger.debug(f"Checkout successful for {commit_hash}.")
            return True
        except Exception as e:
             logger.error(f"Error checking out commit {commit_hash} in {self.repo_path}: {e}", exc_info=False) # Error logged by run_git_command
             return False

    def determine_default_branch(self) -> str:
        """Determines the default branch name using the service's repo path."""
        # This logic often benefits from the GitPython Repo object
        try:
            repo = git.Repo(self.repo_path)
            origin = repo.remotes.origin
            if not repo.heads and not origin.refs:
                logger.warning(f"No local heads or remote refs found in {self.repo_path}. Fetching explicitly.")
                origin.fetch()

            remote_refs = {r.name: r for r in origin.refs}

            for name in ['origin/main', 'origin/master']:
                if name in remote_refs:
                    logger.info(f"Using default branch: {name}")
                    # Return the local tracking branch name or remote ref? Convention matters.
                    # Let's return the remote ref name for clarity in logs.
                    return name

            head_symref = remote_refs.get('origin/HEAD')
            if head_symref and hasattr(head_symref, 'reference'):
                 ref_name = head_symref.reference.name
                 logger.info(f"Determined default branch via origin/HEAD: {ref_name}")
                 return ref_name

            available_refs = [name for name in remote_refs if name != 'origin/HEAD']
            if available_refs:
                fallback_ref = sorted(available_refs)[0]
                logger.warning(f"Could not determine default branch (main/master/HEAD). Using fallback ref: {fallback_ref}")
                return fallback_ref
            else:
                raise ValueError("No suitable remote branch reference found.")

        except (git.GitCommandError, AttributeError, ValueError, Exception) as e:
            logger.error(f"Error determining default branch in {self.repo_path}: {e}", exc_info=True)
            raise ValueError("Failed to determine default branch.") from e