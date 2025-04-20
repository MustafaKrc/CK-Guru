# worker/ingestion/services/steps/prepare_repo.py
import logging
from pathlib import Path
import shutil
from git import Repo, GitCommandError

from .base import IngestionStep, IngestionContext
from shared.core.config import settings

logger = logging.getLogger(__name__)
log_level = getattr(settings, 'LOG_LEVEL', 'INFO')
logger.setLevel(log_level.upper())

def prepare_repository(git_url: str, repo_local_path: Path) -> Repo:
    """Clones or updates the local repository."""
    if repo_local_path.exists():
        logger.info(f"Found existing clone at {repo_local_path}. Fetching updates...")
        try:
            repo = Repo(repo_local_path)
            # Ensure clean state before fetching
            repo.git.reset('--hard')
            repo.git.clean('-fdx')
            origin = repo.remotes.origin
            origin.fetch(prune=True) # Prune deleted remote branches
            logger.info(f"Fetch complete for {repo_local_path}.")
            return repo
        except (GitCommandError, Exception) as e:
            logger.warning(f"Error updating existing repo at {repo_local_path}. Re-cloning. Error: {e}")
            try:
                shutil.rmtree(repo_local_path) # Clean up problematic clone
            except OSError as rm_err:
                logger.error(f"Failed to remove existing clone directory {repo_local_path}: {rm_err}")
                raise # If we can't remove it, we can't clone over it
            # Fall through to clone
    # Clone if it doesn't exist or update failed
    logger.info(f"Cloning {git_url} to {repo_local_path}...")
    # Consider adding depth for large repos if full history isn't always needed immediately
    # no_checkout=True might speed up clone if we checkout specific commits later anyway
    try:
        repo = Repo.clone_from(git_url, repo_local_path, no_checkout=True)
        logger.info(f"Cloning complete.")
    except GitCommandError as e:
         logger.error(f"Failed to clone repository {git_url}: {e}", exc_info=True)
         raise
    return repo

class PrepareRepositoryStep(IngestionStep):
    name = "Prepare Repository"

    def execute(self, context: IngestionContext) -> IngestionContext:
        self._log_info(context, f"Ensuring repository clone exists at {context.repo_local_path}...")
        try:
            # Logic moved to shared function for potential reuse
            context.repo_object = prepare_repository(context.git_url, context.repo_local_path)
            if not context.repo_object: # Double check result
                raise ValueError("Repository object could not be initialized after prepare_repository call.")
            self._log_info(context, "Repository preparation complete.")
        except Exception as e:
            self._log_error(context, f"Repository preparation failed: {e}", exc_info=True)
            raise # Re-raise critical error
        return context