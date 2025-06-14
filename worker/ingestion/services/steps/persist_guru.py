# worker/ingestion/services/steps/persist_guru.py
import asyncio
import logging
from typing import Any, Dict, List

from shared.repositories import CommitGuruMetricRepository

# Import the Pydantic model for type hinting
from shared.schemas.ingestion_data import CommitGuruMetricPayload

from .base import IngestionContext, IngestionStep

logger = logging.getLogger(__name__)


class PersistCommitGuruMetricsStep(IngestionStep):
    name = "Persist Commit Guru Metrics"

    async def execute(
        self, context: IngestionContext, *, guru_repo: CommitGuruMetricRepository
    ) -> IngestionContext:
        """Persists calculated CommitGuru metrics using the repository."""
        # Check the context attribute which now contains Pydantic models
        if not context.raw_commit_guru_data:
            self._log_info(
                context, "No raw Commit Guru data (Pydantic Payloads) to persist."
            )
            return context

        # Type hint for clarity
        commit_payloads: List[CommitGuruMetricPayload] = context.raw_commit_guru_data
        commits_to_upsert: List[Dict[str, Any]] = []
        total_commits = len(commit_payloads)
        processed_count = 0

        self._log_info(
            context,
            f"Preparing {total_commits} Commit Guru metric Payloads for persistence...",
        )
        await self._update_progress(context, f"Preparing {total_commits} commits...", 0)

        # Convert Pydantic models back to dictionaries for the repository's bulk operation
        for i, payload in enumerate(commit_payloads):
            processed_count += 1
            try:
                # Use model_dump to create a dictionary.
                # by_alias=False is likely correct here as the repository expects DB column names
                # (which match the Pydantic field names unless aliases were used AND by_alias=True was specified).
                # Ensure the repository's bulk_upsert expects keys matching the DB model attributes.
                metric_data = payload.model_dump(
                    exclude_unset=True, exclude_none=True
                )  # exclude_none might be useful

                # Add repository_id if not already set during payload creation (should be)
                if "repository_id" not in metric_data:
                    metric_data["repository_id"] = context.repository_id

                # Important: Ensure the keys in metric_data match EXACTLY what the
                # CommitGuruMetricRepository.bulk_upsert method expects for pg_insert.
                # This usually means matching the SQLAlchemy model attribute names.
                commits_to_upsert.append(metric_data)

            except Exception as e:
                # Log error if converting a specific payload fails
                self._log_error(
                    context,
                    f"Error preparing payload for commit {payload.commit_hash[:7]}: {e}",
                    exc_info=False,
                )
                # Continue with the next payload

            if total_commits > 0 and processed_count % 100 == 0:
                step_progress = int(95 * (processed_count / total_commits))
                await self._update_progress(
                    context,
                    f"Preparing Guru ({processed_count}/{total_commits})...",
                    step_progress,
                )

        if commits_to_upsert:
            self._log_info(
                context,
                f"Performing bulk UPSERT for {len(commits_to_upsert)} CommitGuruMetrics...",
            )
            try:
                db_ids_map = await asyncio.to_thread(
                    guru_repo.bulk_upsert, commits_to_upsert
                )
                context.commit_hash_to_db_id_map.update(db_ids_map)
                context.inserted_guru_metrics_count = len(db_ids_map)
                self._log_info(
                    context,
                    f"CommitGuruMetric persistence processed {len(db_ids_map)} records.",
                )
            except Exception as e:
                self._log_error(
                    context, f"CommitGuruMetric persistence failed: {e}", exc_info=True
                )
                raise

        await self._update_progress(context, "Commit Guru persistence complete.", 100)
        return context
