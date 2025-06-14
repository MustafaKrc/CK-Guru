# worker/ingestion/services/steps/ensure_commits_exist.py
import asyncio
import logging

from services.interfaces import IGitService

from .base import IngestionContext, IngestionStep

logger = logging.getLogger(__name__)


class EnsureCommitsExistLocallyStep(IngestionStep):
    name = "Ensure Commits Exist Locally"

    async def execute(
        self, context: IngestionContext, *, git_service: IGitService
    ) -> IngestionContext:
        if not context.is_single_commit_mode:
            self._log_info(
                context, "Skipping local commit check (not single commit mode)."
            )
            return context

        if not context.repo_object:
            raise RuntimeError("Repository object not available for commit check.")
        if not context.target_commit_hash:
            raise ValueError("Target commit hash missing.")

        commits_to_check = [context.target_commit_hash]
        if context.parent_commit_hash:
            commits_to_check.append(context.parent_commit_hash)

        self._log_info(
            context,
            f"Verifying local existence of commits: {', '.join(h[:7] for h in commits_to_check)}",
        )

        for commit_hash in commits_to_check:
            try:
                exists = await asyncio.to_thread(
                    git_service.does_commit_exist, commit_hash
                )
                if exists:
                    self._log_info(
                        context, f"Commit {commit_hash[:7]} verified locally."
                    )
                else:
                    msg = f"Required commit {commit_hash[:7]} not found in local repository clone."
                    self._log_error(context, msg, exc_info=False)
                    raise ValueError(msg)
            except Exception as e:
                msg = f"Unexpected error checking commit {commit_hash[:7]}: {e}"
                self._log_error(context, msg, exc_info=True)
                raise RuntimeError(msg) from e

        return context
