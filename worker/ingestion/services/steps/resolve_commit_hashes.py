# worker/ingestion/services/steps/resolve_commit_hashes.py
import logging
import git
from .base import IngestionStep, IngestionContext
from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

class ResolveCommitHashesStep(IngestionStep):
    name = "Resolve Commit Hashes"

    def execute(self, context: IngestionContext) -> IngestionContext:
        if not context.is_single_commit_mode:
            self._log_info(context, "Skipping hash resolution (not single commit mode).")
            return context

        if not context.repo_object:
            raise RuntimeError("Repository object not available for hash resolution.")
        if not context.target_commit_hash:
            raise ValueError("Target commit hash is missing in context.")

        self._log_info(context, f"Resolving target hash '{context.target_commit_hash}' and finding parent...")

        try:
            # Resolve target hash to full hash
            target_commit_obj = context.repo_object.commit(context.target_commit_hash)
            context.target_commit_hash = target_commit_obj.hexsha # Update context
            self._log_info(context, f"Resolved target commit: {context.target_commit_hash}")

            # Find parent hash
            if not target_commit_obj.parents:
                raise ValueError(f"Target commit {context.target_commit_hash[:7]} is the initial commit and has no parent.")
            # Use first parent
            context.parent_commit_hash = target_commit_obj.parents[0].hexsha
            self._log_info(context, f"Resolved parent commit: {context.parent_commit_hash}")

        except git.BadName as e:
            self._log_error(context, f"Invalid target commit reference: {context.target_commit_hash}", exc_info=False)
            raise ValueError(f"Invalid target commit reference: {context.target_commit_hash}") from e
        except ValueError as e: # Catch specific error from no parent case
                self._log_error(context, str(e), exc_info=False)
                raise e
        except Exception as e:
            self._log_error(context, f"Error resolving commit hashes: {e}", exc_info=True)
            raise RuntimeError("Failed to resolve commit hashes.") from e

        return context