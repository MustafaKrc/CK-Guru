# worker/ingestion/services/steps/persist_commit_details.py
import asyncio
import logging

from shared.repositories import CommitDetailsRepository

from .base import IngestionContext, IngestionStep

logger = logging.getLogger(__name__)


class PersistCommitDetailsStep(IngestionStep):
    name = "Persist Commit Details"

    async def execute(
        self, context: IngestionContext, *, commit_details_repo: CommitDetailsRepository
    ) -> IngestionContext:
        if not context.commit_details_payloads:
            self._log_info(context, "No new commit details to persist.")
            return context
        
        self._log_info(context, f"Persisting details for {len(context.commit_details_payloads)} commit(s).")
        
        for commit_hash, payload in context.commit_details_payloads.items():
            try:
                await asyncio.to_thread(commit_details_repo.upsert_from_payload, payload)
                self._log_info(context, f"Successfully persisted details for commit {commit_hash[:7]}")
            except Exception as e:
                self._log_error(context, f"Failed to persist details for commit {commit_hash}: {e}", exc_info=True)
                context.warnings.append(f"Failed to persist details for {commit_hash[:7]}")
        
        return context