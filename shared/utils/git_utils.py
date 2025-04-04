# worker/app/tasks/utils/git_utils.py
import logging
import subprocess
from typing import Optional
from pathlib import Path

import git

from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

def run_git_command(cmd: str, cwd: Path) -> str:
    """Helper to run git commands and handle errors."""
    try:
        # Reduced logging noise for successful commands
        # logger.debug(f"Running git command in {cwd}: {cmd[:100]}...")
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, check=True, capture_output=True,
            text=True, encoding='utf-8', errors='ignore'
        )
        # logger.debug(f"Git command successful. Stdout length: {len(result.stdout)}")
        if result.stderr:
             logger.warning(f"Git command stderr: {result.stderr.strip()}")
        return result.stdout
    except subprocess.CalledProcessError as e:
        # Log error details without raising immediately, allow caller to handle
        error_message = (
            f"Git command failed (exit code {e.returncode}) in {cwd}.\n"
            f"Command: {e.cmd}\nStderr: {e.stderr.strip()}"
        )
        logger.error(error_message)
        raise # Re-raise the exception
    except FileNotFoundError:
        logger.error(f"Git command not found. Ensure git is installed and in PATH.")
        raise
    except Exception as e:
        logger.error(f"Unexpected error running git command '{cmd[:100]}...' in {cwd}: {e}", exc_info=True)
        raise

def find_commit_hash_before_timestamp(repo_path: Path, timestamp: int) -> Optional[str]:
    """
    Finds the hash of the latest commit made strictly *before* a given Unix timestamp.

    Args:
        repo_path: Path to the git repository.
        timestamp: The Unix timestamp (integer seconds since epoch).

    Returns:
        The commit hash (str) or None if no such commit exists.
    """
    # git rev-list: List commits in reverse chronological order
    # -n 1: Limit to 1 commit
    # --before=<timestamp>: Filter commits before the timestamp
    # HEAD: Start searching from the current HEAD (or specify a branch)
    # Using --first-parent might speed things up on complex histories if desired
    cmd = f'git rev-list -n 1 --before={timestamp} HEAD'
    try:
        commit_hash = run_git_command(cmd, cwd=repo_path).strip()
        if commit_hash and len(commit_hash) == 40: # Basic validation
            logger.debug(f"Found commit {commit_hash[:7]} before timestamp {timestamp}")
            return commit_hash
        else:
            logger.warning(f"No commit found before timestamp {timestamp} in {repo_path}")
            return None
    except subprocess.CalledProcessError:
        # This can happen if the timestamp is before the first commit
        logger.warning(f"Could not find any commit before timestamp {timestamp} in {repo_path} (possibly too early).")
        return None
    except Exception as e:
        logger.error(f"Error finding commit before timestamp {timestamp}: {e}", exc_info=True)
        return None
    
def checkout_commit(repo: git.Repo, commit_hash: str) -> bool:
    """Checks out the repository at the specified commit. Returns True on success."""
    try:
        logger.debug(f"Checking out commit {commit_hash}...")
        # Clean state before checkout is crucial
        repo.git.reset('--hard')
        repo.git.clean('-fdx')
        repo.git.checkout(commit_hash, force=True)
        logger.debug(f"Checkout successful for {commit_hash}.")
        return True
    except git.GitCommandError as e:
        logger.error(f"Error checking out commit {commit_hash}: {e.stderr}")
        return False
    except Exception as e:
         logger.error(f"Unexpected error during checkout of {commit_hash}: {e}", exc_info=True)
         return False
    
def determine_default_branch(repo: git.Repo) -> str:
    """Determines the default branch name."""
    try:
        origin = repo.remotes.origin
        if not repo.heads and not origin.refs: # Handle empty repo
             logger.warning(f"No local heads or remote refs found. Fetching explicitly.")
             origin.fetch()

        remote_refs = {r.name: r for r in origin.refs} # Map name to ref object

        # Try common names first
        for name in ['origin/main', 'origin/master']:
            if name in remote_refs:
                logger.info(f"Using default branch: {name}")
                return name

        # Try origin/HEAD symbolic reference
        head_symref = remote_refs.get('origin/HEAD')
        if head_symref and hasattr(head_symref, 'reference'):
             ref_name = head_symref.reference.name
             logger.info(f"Determined default branch via origin/HEAD: {ref_name}")
             return ref_name

        # Last resort: pick the first available remote branch (excluding HEAD)
        available_refs = [name for name in remote_refs if name != 'origin/HEAD']
        if available_refs:
            fallback_ref = sorted(available_refs)[0] # Sort for some determinism
            logger.warning(f"Could not determine default branch (main/master/HEAD). Using fallback ref: {fallback_ref}")
            return fallback_ref
        else:
            raise ValueError("No suitable remote branch reference found for CK analysis.")

    except (git.GitCommandError, AttributeError, ValueError, Exception) as e:
        logger.error(f"Error determining default branch: {e}", exc_info=True)
        raise ValueError("Failed to determine default branch.") from e