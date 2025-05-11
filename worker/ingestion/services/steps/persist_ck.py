# worker/ingestion/services/steps/persist_ck.py
import logging
from typing import Any, Dict, List  # Add List, Any

from shared.repositories import CKMetricRepository

# Import the Pydantic model for type hinting
from .base import IngestionContext, IngestionStep

logger = logging.getLogger(__name__)


class PersistCKMetricsStep(IngestionStep):
    name = "Persist CK Metrics"

    def execute(
        self, context: IngestionContext, *, ck_repo: CKMetricRepository
    ) -> IngestionContext:
        # Check the context attribute which now contains Pydantic models
        if not context.raw_ck_metrics:
            self._log_info(
                context, "No raw CK metrics data (Pydantic Payloads) to persist."
            )
            return context

        inserted_count = 0
        total_commits_to_process = len(context.raw_ck_metrics)
        processed_commit_count = 0

        log_msg_prefix = (
            f"Persisting CK metrics Payloads for {total_commits_to_process} commits..."
        )

        self._log_info(context, log_msg_prefix)
        self._update_progress(context, log_msg_prefix, 0)

        all_instances_to_upsert: List[Dict[str, Any]] = []
        # Iterate through the dictionary {commit_hash: List[CKMetricPayload]}
        for commit_hash, payload_list in context.raw_ck_metrics.items():
            processed_commit_count += 1
            if not payload_list:  # Skip commits with empty lists
                continue

            # Convert list of Pydantic models to list of dictionaries
            for payload in payload_list:
                try:
                    metric_data = payload.model_dump(
                        exclude_unset=True, exclude_none=True
                    )

                    # Add repository_id and commit_hash if not already set
                    if "repository_id" not in metric_data:
                        metric_data["repository_id"] = context.repository_id
                    if "commit_hash" not in metric_data:
                        metric_data["commit_hash"] = commit_hash

                    # Optional: Add a final validation check if needed, though Pydantic model should be correct
                    # Ensure required fields like 'file' are present
                    if "file" not in metric_data or not metric_data["file"]:
                        logger.warning(
                            f"CK Payload missing 'file' for commit {commit_hash[:7]}. Skipping record."
                        )
                        continue

                    # Ensure keys match DB model attributes expected by repository
                    # Note: model_dump(by_alias=True) converts 'class_name' back to 'class', 'type_' to 'type', etc.
                    # The CKMetricRepository's bulk_upsert needs to expect these potentially aliased names
                    # if it builds the SQL insert directly, OR SQLAlchemy handles the model-to-DB mapping.
                    # Assuming SQLAlchemy handles the mapping based on the model definition.
                    # If passing raw dicts to pg_insert, ensure keys match DB *column* names.
                    # Let's adjust the dump to *not* use alias, relying on SQLAlchemy mapping.
                    metric_data_db = payload.model_dump(
                        exclude_unset=True, exclude_none=True
                    )
                    # Add IDs again
                    metric_data_db["repository_id"] = context.repository_id
                    metric_data_db["commit_hash"] = commit_hash
                    if "file" not in metric_data_db or not metric_data_db["file"]:
                        continue  # Sanity check file again

                    all_instances_to_upsert.append(metric_data_db)

                except Exception as e:
                    logger.error(
                        f"Error preparing CK payload for commit {commit_hash[:7]}: {e}",
                        exc_info=False,
                    )

            # Update progress periodically
            if total_commits_to_process > 0 and processed_commit_count % 50 == 0:
                step_progress = int(
                    95 * (processed_commit_count / total_commits_to_process)
                )
                self._update_progress(
                    context,
                    f"Preparing CK ({processed_commit_count}/{total_commits_to_process})...",
                    step_progress,
                )

        # --- Perform Bulk UPSERT using the repository ---
        if all_instances_to_upsert:
            self._log_info(
                context,
                f"Attempting bulk UPSERT for {len(all_instances_to_upsert)} CK records...",
            )
            try:
                processed_count = ck_repo.bulk_upsert(all_instances_to_upsert)
                inserted_count = processed_count  # UPSERT count is treated as processed
            except Exception as e:
                self._log_error(
                    context, f"CKMetric persistence failed: {e}", exc_info=True
                )
                raise

        context.inserted_ck_metrics_count = inserted_count
        self._log_info(
            context,
            f"Persisted {inserted_count} CK metric records for {processed_commit_count} commits.",
        )
        self._update_progress(context, "CK persistence complete.", 100)
        return context
