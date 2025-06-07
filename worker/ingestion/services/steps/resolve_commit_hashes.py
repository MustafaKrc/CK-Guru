# worker/ingestion/services/steps/resolve_commit_hashes.py
import asyncio
import logging
from typing import Set

from services.git_service import GitCommandError, GitRefNotFoundError, GitService
from shared.core.config import settings
from shared.repositories import CommitGuruMetricRepository

from .base import IngestionContext, IngestionStep

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


class ResolveCommitHashesStep(IngestionStep):
    name = "Resolve Commit Hashes"

    async def execute(
        self,
        context: IngestionContext,
        *,
        git_service: GitService,
        guru_repo: CommitGuruMetricRepository,
    ) -> IngestionContext:

        if not context.repo_object:
            raise RuntimeError("Repository object not available for hash resolution.")

        # --- Logic for Full History Mode ---
        if not context.is_single_commit_mode:
            self._log_info(context, "Resolving all commit hashes for default branch.")
            default_branch_ref = await asyncio.to_thread(
                git_service.determine_default_branch
            )
            commits_iterator = context.repo_object.iter_commits(rev=default_branch_ref)
            context.commits_to_process = [c.hexsha for c in commits_iterator]
            self._log_info(
                context,
                f"Found {len(context.commits_to_process)} commits for full history processing.",
            )
            return context

        # --- Logic for Single Commit Mode (with recursive parent search) ---
        if not context.target_commit_hash:
            raise ValueError("Target commit hash is missing in single-commit mode.")

        original_target_ref = context.target_commit_hash
        self._log_info(
            context,
            f"Resolving target ref '{original_target_ref}' and walking parent history...",
        )

        try:
            # 1. Resolve the initial target hash
            resolved_target_hash = await asyncio.to_thread(
                git_service.resolve_ref_to_hash, original_target_ref
            )
            context.target_commit_hash = resolved_target_hash
            self._log_info(
                context, f"Resolved target commit: {context.target_commit_hash}"
            )

            # 2. Walk backwards from the target commit until an ingested parent is found
            commits_to_ingest: list[str] = []
            visited_hashes: Set[str] = set()
            current_hash: str | None = context.target_commit_hash

            MAX_RECURSION_DEPTH = 100 # Safety break
            recursion_count = 0

            while current_hash and current_hash not in visited_hashes and recursion_count < MAX_RECURSION_DEPTH:
                recursion_count += 1
                visited_hashes.add(current_hash)
                
                # Check if this commit's metrics already exist
                existing_metric = await asyncio.to_thread(
                    guru_repo.get_by_hash, context.repository_id, current_hash
                )
                
                if existing_metric:
                    self._log_info(context, f"Found already ingested ancestor: {current_hash[:7]}. Stopping walk.")
                    break # Stop: We found the boundary
                else:
                    # This commit needs to be processed
                    commits_to_ingest.append(current_hash)
                    self._log_info(context, f"Commit {current_hash[:7]} needs ingestion. Adding to queue.")
                    
                    # Move to the next parent
                    parent_hash = await asyncio.to_thread(
                        git_service.get_first_parent_hash, current_hash
                    )
                    current_hash = parent_hash
            
            if recursion_count >= MAX_RECURSION_DEPTH:
                self._log_warning(context, f"Reached max recursion depth ({MAX_RECURSION_DEPTH}) walking parent history. Stopping.")

            # The list is built from child -> parent, but pipeline should process parent -> child. Reverse it.
            context.commits_to_process = list(reversed(commits_to_ingest))
            
            # For clarity, still set the immediate parent in the context, as other steps might rely on it.
            if len(commits_to_ingest) > 1:
                context.parent_commit_hash = commits_to_ingest[1] # The second item added was the immediate parent
            elif context.target_commit_hash:
                 context.parent_commit_hash = await asyncio.to_thread(git_service.get_first_parent_hash, context.target_commit_hash)
            
            if not context.commits_to_process:
                 self._log_warning(context, f"Target commit {context.target_commit_hash[:7]} seems to be already ingested. No new commits to process.")
            else:
                 self._log_info(context, f"Final list of commits to process: {len(context.commits_to_process)}")


        except GitRefNotFoundError as e:
            self._log_error(context, str(e), exc_info=False)
            raise ValueError(str(e)) from e
        except GitCommandError as e:
            self._log_error(
                context, f"Git command error during hash resolution: {e}", exc_info=True
            )
            raise RuntimeError("Git command failed during hash resolution.") from e
        except Exception as e:
            self._log_error(
                context, f"Unexpected error resolving commit hashes: {e}", exc_info=True
            )
            raise RuntimeError("Failed to resolve commit hashes.") from e

        return context