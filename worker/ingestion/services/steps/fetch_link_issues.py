# worker/ingestion/services/steps/fetch_link_issues.py
import asyncio
import logging
from typing import Dict, List

from services.interfaces import IRepositoryApiClient
from shared.core.config import settings
from shared.repositories import CommitGuruMetricRepository, GitHubIssueRepository

from .base import IngestionContext, IngestionStep

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


class FetchAndLinkIssuesStep(IngestionStep):
    name = "Fetch/Link GitHub Issues"

    async def execute(
        self,
        context: IngestionContext,
        *,
        github_repo: GitHubIssueRepository,
        guru_repo: CommitGuruMetricRepository,
        repository_api_client: IRepositoryApiClient,
    ) -> IngestionContext:
        """Fetches/updates GitHub issues and links them to persisted commit metrics."""

        owner, repo_name = None, None
        repo_info = repository_api_client.extract_repo_owner_name(context.git_url)
        if not repo_info:
            self._log_warning(
                context,
                f"Could not extract owner/repo from {context.git_url}. Skipping GitHub issue linking.",
            )
            return context
        owner, repo_name = repo_info

        if not context.commit_hash_to_db_id_map:
            self._log_info(context, "Commit hash map is empty, cannot link issues.")
            return context

        # Reconstruct the commit_hash -> issue_numbers map needed for linking
        commit_hash_to_issue_numbers: Dict[str, List[str]] = {}
        for payload in context.raw_commit_guru_data:
            if payload.commit_message:  # Check if message exists
                issue_numbers = repository_api_client.extract_issue_ids(
                    payload.commit_message
                )
                if issue_numbers:
                    commit_hash_to_issue_numbers[payload.commit_hash] = issue_numbers

        if not commit_hash_to_issue_numbers:
            self._log_info(
                context, "No issue numbers found in commit messages to link."
            )
            return context

        self._log_info(
            context,
            f"Linking issues for {len(commit_hash_to_issue_numbers)} commits...",
        )
        await self._update_progress(context, "Linking GitHub issues...", 0)
        processed_link_count = 0
        total_links_to_process = len(commit_hash_to_issue_numbers)

        for commit_hash, issue_numbers in commit_hash_to_issue_numbers.items():
            processed_link_count += 1
            commit_db_id = context.commit_hash_to_db_id_map.get(commit_hash)
            if not commit_db_id or commit_db_id == -1:  # Check if ID is valid
                self._log_warning(
                    context,
                    f"Skipping issue linking for {commit_hash[:7]}, DB ID not found or invalid.",
                )
                continue

            linked_issue_db_ids_for_commit: List[int] = []
            for number_str in issue_numbers:
                try:
                    issue_number = int(number_str)
                except ValueError:
                    continue

                # Fetch issue data from GitHub API
                api_response = await asyncio.to_thread(
                    repository_api_client.get_issue, owner, repo_name, number_str
                )

                # Update or Create Issue in DB using the repository
                issue_obj = await asyncio.to_thread(
                    github_repo.update_or_create_from_api,
                    context.repository_id,
                    issue_number,
                    api_response,
                )

                if issue_obj and issue_obj.id:
                    linked_issue_db_ids_for_commit.append(issue_obj.id)
                elif api_response.status_code not in [
                    404,
                    410,
                ]:  # Log if not found isn't the reason
                    self._log_warning(
                        context,
                        f"Failed to get/create DB entry for issue #{issue_number} for commit {commit_hash[:7]}. API Status: {api_response.status_code}",
                    )

            # Link the successfully processed issues to the commit metric
            if linked_issue_db_ids_for_commit:
                try:
                    # Use the CommitGuruMetricRepository to handle the linking
                    await asyncio.to_thread(
                        guru_repo.link_issues_to_commit,
                        commit_db_id,
                        linked_issue_db_ids_for_commit,
                    )
                    self._log_debug(
                        context,
                        f"Attempted linking {len(linked_issue_db_ids_for_commit)} issues to commit ID {commit_db_id}.",
                    )
                except Exception as link_err:
                    # Log error but continue processing other commits
                    self._log_error(
                        context,
                        f"Failed linking issues for commit ID {commit_db_id}: {link_err}",
                        exc_info=False,
                    )

            # Update progress periodically
            if total_links_to_process > 0 and processed_link_count % 50 == 0:
                step_progress = int(
                    100 * (processed_link_count / total_links_to_process)
                )
                await self._update_progress(
                    context,
                    f"Linking issues ({processed_link_count}/{total_links_to_process})...",
                    step_progress,
                )

        self._log_info(context, "Finished linking GitHub issues.")
        await self._update_progress(context, "Issue linking complete.", 100)
        return context
