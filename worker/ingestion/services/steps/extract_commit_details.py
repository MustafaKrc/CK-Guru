# worker/ingestion/services/steps/extract_commit_details.py
import asyncio
import logging

from shared.repositories import CommitDetailsRepository
from shared.schemas.enums import CommitIngestionStatusEnum, FileChangeTypeEnum

from .base import IngestionContext, IngestionStep

logger = logging.getLogger(__name__)


class ExtractCommitDetailsStep(IngestionStep):
    name = "Extract Commit Details"

    async def execute(
        self, context: IngestionContext, *, commit_details_repo: CommitDetailsRepository
    ) -> IngestionContext:
        
        if not context.repo_object:
            raise RuntimeError("Repository object not available for commit detail extraction.")

        if not context.commits_to_process:
            self._log_warning(context, "No commits to process. Skipping detail extraction.")
            return context

        self._log_info(context, f"Extracting details for {len(context.commits_to_process)} commit(s).")
        
        for commit_hash in context.commits_to_process:
            try:
                # Check if details are already complete in DB
                existing_details = await asyncio.to_thread(
                    commit_details_repo.get_by_hash, context.repository_id, commit_hash
                )
                if existing_details and existing_details.ingestion_status == CommitIngestionStatusEnum.COMPLETE:
                    self._log_info(context, f"Details for commit {commit_hash[:7]} already complete. Skipping extraction.")
                    continue

                commit_obj = context.repo_object.commit(commit_hash)
                parent = commit_obj.parents[0] if commit_obj.parents else None
                diff_list = commit_obj.diff(parent, create_patch=True, R=True) # R=True to detect renames

                detail_data = {
                    "repository_id": context.repository_id,
                    "commit_hash": commit_obj.hexsha,
                    "author_name": commit_obj.author.name,
                    "author_email": commit_obj.author.email,
                    "author_date": commit_obj.authored_datetime,
                    "committer_name": commit_obj.committer.name,
                    "committer_email": commit_obj.committer.email,
                    "committer_date": commit_obj.committed_datetime,
                    "message": commit_obj.message,
                    "parents": [p.hexsha for p in commit_obj.parents],
                    "stats_insertions": commit_obj.stats.total['insertions'],
                    "stats_deletions": commit_obj.stats.total['deletions'],
                    "stats_files_changed": commit_obj.stats.total['files'],
                    "ingestion_status": CommitIngestionStatusEnum.COMPLETE.value,
                    "status_message": "Ingestion completed successfully."
                }
                
                diff_data_list = []
                for diff in diff_list:
                    # TODO: check this enum conversion logic.
                    # diff.change_type may not work as expected
                    try:
                        change_type_enum = FileChangeTypeEnum(diff.change_type).value
                    except ValueError:
                        change_type_enum = FileChangeTypeEnum.X.value

                    diff_data = {
                        "file_path": diff.b_path or diff.a_path,
                        "change_type": change_type_enum,
                        "old_path": diff.a_path if diff.renamed else None,
                        "diff_text": diff.diff.decode('utf-8', 'ignore') if diff.diff else '',
                        "insertions": diff.diff.count(b'\n+') if diff.diff else 0,
                        "deletions": diff.diff.count(b'\n-') if diff.diff else 0,
                    }
                    diff_data_list.append(diff_data)
                
                context.commit_details_payloads[commit_hash] = {
                    "details": detail_data, 
                    "diffs": diff_data_list
                }
                self._log_info(context, f"Extracted details for commit {commit_hash[:7]}")

            except Exception as e:
                self._log_error(context, f"Failed to extract details for commit {commit_hash}: {e}", exc_info=True)
                context.warnings.append(f"Failed extraction for {commit_hash[:7]}")

        return context