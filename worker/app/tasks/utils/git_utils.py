# worker/app/tasks/utils/git_utils.py
import logging
import subprocess
from pathlib import Path
from typing import Optional
import git # Import GitPython

logger = logging.getLogger(__name__)

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