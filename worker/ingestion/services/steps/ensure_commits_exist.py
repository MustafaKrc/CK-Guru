# worker/ingestion/services/steps/ensure_commits_exist.py
import logging
import git
from .base import IngestionStep, IngestionContext
from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

class EnsureCommitsExistLocallyStep(IngestionStep):
    name = "Ensure Commits Exist Locally"

    def execute(self, context: IngestionContext) -> IngestionContext:
        if not context.is_single_commit_mode:
            self._log_info(context, "Skipping local commit check (not single commit mode).")
            return context

        if not context.repo_object:
            raise RuntimeError("Repository object not available for commit check.")
        if not context.target_commit_hash:
            raise ValueError("Target commit hash missing.")
        # Parent hash might be None for initial commit, but Resolve step should handle that.
        # We primarily check target and parent *if* parent exists.

        commits_to_check = [context.target_commit_hash]
        if context.parent_commit_hash:
            commits_to_check.append(context.parent_commit_hash)

        self._log_info(context, f"Verifying local existence of commits: {', '.join(h[:7] for h in commits_to_check)}")

        for commit_hash in commits_to_check:
            try:
                context.repo_object.commit(commit_hash) # Attempt to access commit
                self._log_info(context, f"Commit {commit_hash[:7]} verified locally.")
            except (git.BadName, ValueError) as e:
                # This indicates the commit (resolved full hash) is not in the local repo history.
                # Could happen if clone depth was insufficient or repo history changed.
                msg = f"Required commit {commit_hash[:7]} not found in local repository clone."
                self._log_error(context, msg, exc_info=False)
                raise ValueError(msg) from e
            except Exception as e:
                    msg = f"Unexpected error checking commit {commit_hash[:7]}: {e}"
                    self._log_error(context, msg, exc_info=True)
                    raise RuntimeError(msg) from e

        return context