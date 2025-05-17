# worker/ingestion/services/steps/prepare_repo.py
import logging
import shutil
import asyncio
from pathlib import Path

# Use GitPython directly for this step's core function
from git import GitCommandError, Repo

from shared.core.config import settings  # Keep settings import

from .base import IngestionContext, IngestionStep

logger = logging.getLogger(__name__)
log_level = getattr(settings, "LOG_LEVEL", "INFO")
logger.setLevel(log_level.upper())


# Must prepare repo without git_service
# because git_service expects a repo to be present
# and we are preparing it in this step
def _ensure_repository_prepared(git_url: str, repo_local_path: Path) -> Repo:
    """Clones or updates the local repository."""
    # Ensure parent directory exists BEFORE checking/cloning
    try:
        repo_local_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.critical(
            f"Failed to create base directory {repo_local_path.parent}: {e}",
            exc_info=True,
        )
        # Re-raise a more specific error or just let it propagate
        raise FileNotFoundError(
            f"Cannot proceed: Failed to create required directory {repo_local_path.parent}"
        ) from e

    if repo_local_path.is_dir():  # Check if it's a directory specifically
        logger.info(f"Found existing clone at {repo_local_path}. Fetching updates...")
        try:
            repo = Repo(repo_local_path)
            # Ensure clean state before fetching
            repo.git.reset("--hard", "--quiet")
            repo.git.clean("-fdx", "--quiet")
            origin = repo.remotes.origin
            origin.fetch(prune=True)
            logger.info(f"Fetch complete for {repo_local_path}.")
            return repo
        except (GitCommandError, Exception) as e:
            logger.warning(
                f"Error updating existing repo at {repo_local_path}. Re-cloning. Error: {e}"
            )
            try:
                shutil.rmtree(repo_local_path)
            except OSError as rm_err:
                logger.error(
                    f"Failed to remove existing clone directory {repo_local_path}: {rm_err}"
                )
                raise FileNotFoundError(
                    f"Failed to clean up existing broken clone at {repo_local_path}"
                ) from rm_err
            # Fall through to clone
    elif repo_local_path.exists():  # Path exists but is not a directory
        logger.error(
            f"Path {repo_local_path} exists but is not a directory. Attempting removal."
        )
        try:
            repo_local_path.unlink()  # Try removing as file first
            repo_local_path.parent.mkdir(
                parents=True, exist_ok=True
            )  # Ensure parent exists again
        except OSError as rm_err:
            logger.error(
                f"Failed to remove existing file at {repo_local_path}: {rm_err}"
            )
            raise FileNotFoundError(
                f"Path exists but is not a directory and cannot be removed: {repo_local_path}"
            ) from rm_err

    # Clone if it doesn't exist or update failed/path cleaned
    logger.info(f"Cloning {git_url} to {repo_local_path}...")
    try:
        # clone_from handles directory creation
        repo = Repo.clone_from(git_url, repo_local_path, no_checkout=True)
        logger.info("Cloning complete.")
        return repo  # Return the new Repo object
    except GitCommandError as e:
        logger.error(f"Failed to clone repository {git_url}: {e}", exc_info=True)
        # Raise a standard exception type perhaps? Or keep GitCommandError?
        raise  # Re-raise the original error
    except Exception as e:
        logger.error(f"Unexpected error during clone of {git_url}: {e}", exc_info=True)
        raise RuntimeError(f"Unexpected error during clone: {e}") from e


class PrepareRepositoryStep(IngestionStep):
    name = "Prepare Repository"

    async def execute(self, context: IngestionContext, **kwargs) -> IngestionContext:
        self._log_info(context, f"Ensuring clone at {context.repo_local_path}")
        try:
            repo = await asyncio.to_thread(_ensure_repository_prepared, context.git_url, context.repo_local_path)
            context.repo_object = repo or None
            if not repo:
                raise ValueError("Repo object missing")
            self._log_info(context, "Repository prepared")
        except Exception as e:
            self._log_error(context, f"Preparation failed: {e}", exc_info=True)
            context.repo_object = None
            raise
        return context
