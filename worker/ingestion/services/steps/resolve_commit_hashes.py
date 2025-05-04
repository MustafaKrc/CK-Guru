# worker/ingestion/services/steps/resolve_commit_hashes.py
import logging

from services.git_service import GitService, GitRefNotFoundError, GitCommandError
from .base import IngestionStep, IngestionContext
from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

class ResolveCommitHashesStep(IngestionStep):
    name = "Resolve Commit Hashes"

    def execute(self, context: IngestionContext, *, git_service: GitService) -> IngestionContext: # Inject service
        if not context.is_single_commit_mode:
            self._log_info(context, "Skipping hash resolution (not single commit mode).")
            return context

        if not context.repo_object:
           raise RuntimeError("Repository object not available for hash resolution.")
        if not context.target_commit_hash:
            raise ValueError("Target commit hash is missing in context.")

        original_target_ref = context.target_commit_hash # Keep original for logging
        self._log_info(context, f"Resolving target ref '{original_target_ref}' and finding parent...")

        try:
            # Resolve target hash using GitService
            resolved_target_hash = git_service.resolve_ref_to_hash(original_target_ref)
            context.target_commit_hash = resolved_target_hash # Update context with full hash
            self._log_info(context, f"Resolved target commit: {context.target_commit_hash}")

            # Find parent hash using GitService
            parent_hash = git_service.get_first_parent_hash(context.target_commit_hash)
            if parent_hash:
                context.parent_commit_hash = parent_hash
                self._log_info(context, f"Resolved parent commit: {context.parent_commit_hash}")
            else:
                # This case (initial commit) should ideally be handled gracefully downstream
                # Or raise a specific exception if single-commit mode cannot handle initial commits
                self._log_warning(context, f"Target commit {context.target_commit_hash[:7]} has no parent (initial commit).")
                context.parent_commit_hash = None # Explicitly set to None

        except GitRefNotFoundError as e:
            # Handle specific error for invalid ref
            self._log_error(context, str(e), exc_info=False)
            raise ValueError(str(e)) from e # Re-raise as ValueError for pipeline handling?
        except GitCommandError as e:
            # Handle other git command errors during resolution
            self._log_error(context, f"Git command error during hash resolution: {e}", exc_info=True)
            raise RuntimeError("Git command failed during hash resolution.") from e
        except Exception as e:
            self._log_error(context, f"Unexpected error resolving commit hashes: {e}", exc_info=True)
            raise RuntimeError("Failed to resolve commit hashes.") from e

        return context