# worker/ingestion/services/steps/link_bugs.py
import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple

from services.bug_linker import GitCommitLinker
from services.git_service import GitService
from shared.core.config import settings

# Import Repositories
from shared.repositories import CommitGuruMetricRepository

from .base import IngestionContext, IngestionStep

logger = logging.getLogger(__name__)
log_level = getattr(settings, "LOG_LEVEL", "INFO")
logger.setLevel(log_level.upper())


class LinkBugsStep(IngestionStep):
    name = "Link Bugs"

    async def execute(
        self,
        context: IngestionContext,
        *,
        guru_repo: CommitGuruMetricRepository,
        git_service: GitService,
    ) -> IngestionContext:

        corrective_info: Dict[str, Optional[int]] = {}

        if not context.commit_hash_to_db_id_map:
            self._log_info(
                context,
                "Commit hash map is empty, cannot determine corrective commits.",
            )
            return context

        self._log_info(
            context,
            "Preparing data for bug linking (checking keywords and issue timestamps)...",
        )
        await self._update_progress(
            context, "Checking fix keywords and issue links...", 0
        )

        # Query timestamps using the GitHubIssueRepository
        processed_corrective_count = 0
        total_potential_corrective = sum(
            1 for is_fix in context.commit_fix_keyword_map.values() if is_fix
        )
        self._log_info(
            context,
            f"Found {total_potential_corrective} potential corrective commits based on keywords.",
        )

        # Temporary list to hold (hash, db_id) for timestamp query
        commits_for_ts_query: List[Tuple[str, int]] = []
        for commit_hash, db_id in context.commit_hash_to_db_id_map.items():
            if db_id != -1 and context.commit_fix_keyword_map.get(commit_hash, False):
                commits_for_ts_query.append((commit_hash, db_id))

        # Fetch timestamps (Consider if this needs optimization or batching within the repo)
        for commit_hash, db_id in commits_for_ts_query:
            processed_corrective_count += 1
            ts = await asyncio.to_thread(
                guru_repo.get_earliest_linked_issue_timestamp, db_id
            )
            corrective_info[commit_hash] = ts
            if processed_corrective_count % 50 == 0:
                progress = (
                    int(20 * (processed_corrective_count / total_potential_corrective))
                    if total_potential_corrective
                    else 0
                )
                await self._update_progress(
                    context,
                    f"Checking timestamps ({processed_corrective_count}/{total_potential_corrective})...",
                    progress,
                )

        self._log_info(
            context,
            f"Prepared {len(corrective_info)} corrective commits with timestamps for linking.",
        )
        await self._update_progress(context, "Running GitCommitLinker...", 20)

        if not corrective_info:
            self._log_info(
                context, "No corrective commits found, skipping bug linking analysis."
            )
            return context

        if not context.repo_local_path or not context.repo_local_path.is_dir():
            self._log_warning(
                context, "Repository path invalid, skipping bug linking analysis."
            )
            return context

        try:
            linker = GitCommitLinker(git_service)
            map_hash = await asyncio.to_thread(
                linker.link_corrective_commits, corrective_info
            )
            context.bug_link_map_hash = map_hash
            self._log_info(
                context,
                f"Bug linking analysis identified {len(context.bug_link_map_hash)} potential bug-introducing commits (by hash).",
            )
            await self._update_progress(
                context, "Bug linking analysis complete. Updating database...", 80
            )
        except Exception as e:
            self._log_error(context, f"Bug linking analysis failed: {e}", exc_info=True)
            self._log_warning(
                context, "Bug linking analysis failed, proceeding without updates."
            )
            return context

        # Update DB using the CommitGuruMetricRepository
        if context.bug_link_map_hash:
            self._log_info(
                context, "Updating bug flags and fixing hashes in database..."
            )
            bug_introducing_commit_ids: Set[int] = set()
            fixing_commit_map_for_update: Dict[int, List[str]] = {}

            for buggy_hash, fixing_hashes in context.bug_link_map_hash.items():
                buggy_db_id = context.commit_hash_to_db_id_map.get(buggy_hash, -1)
                if buggy_db_id != -1:
                    bug_introducing_commit_ids.add(buggy_db_id)
                    fixing_commit_map_for_update[buggy_db_id] = fixing_hashes
                else:
                    self._log_warning(
                        context,
                        f"Could not find DB ID for potential buggy commit hash {buggy_hash[:7]}. Cannot update.",
                    )

            if bug_introducing_commit_ids or fixing_commit_map_for_update:
                try:
                    await asyncio.to_thread(
                        guru_repo.update_bug_links,
                        bug_introducing_commit_ids,
                        fixing_commit_map_for_update,
                    )
                    self._log_info(
                        context,
                        "Database successfully updated with bug link information.",
                    )
                except Exception as e:
                    self._log_error(
                        context,
                        f"Failed to update DB with bug links via repository: {e}",
                        exc_info=True,
                    )
                    self._log_warning(
                        context, "Failed to update DB with bug links."
                    )  # Add warning to context
            else:
                self._log_info(
                    context, "No bug links found requiring database updates."
                )

        await self._update_progress(context, "Bug linking step complete.", 100)
        return context
