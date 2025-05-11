# worker/ingestion/services/steps/calculate_ck.py
import logging
from typing import List

from pydantic import ValidationError

from services.interfaces import ICKRunnerService, IGitService
from shared.core.config import settings
from shared.repositories import CKMetricRepository
from shared.schemas.ingestion_data import CKMetricPayload

from .base import IngestionContext, IngestionStep

logger = logging.getLogger(__name__)
log_level = getattr(settings, "LOG_LEVEL", "INFO")
logger.setLevel(log_level.upper())


class CalculateCKMetricsStep(IngestionStep):
    name = "Calculate CK Metrics"

    def execute(
        self,
        context: IngestionContext,
        *,
        ck_runner: ICKRunnerService,
        ck_repo: CKMetricRepository,
        git_service: IGitService,
    ) -> IngestionContext:
        if not context.repo_object:
            self._log_warning(
                context, "Repository object not available, skipping CK analysis."
            )
            return context

        context.raw_ck_metrics = {}
        original_head = None
        try:
            original_head = context.repo_object.head.commit.hexsha
            self._log_info(context, f"Stored original HEAD: {original_head[:7]}")
        except Exception as head_err:
            self._log_warning(
                context,
                f"Could not determine original HEAD: {head_err}. Checkout back might fail.",
            )

        local_branch_name = "unknown_branch"  # Keep track for final checkout

        try:
            commits_to_process_hashes: List[str] = []
            # Determine commits to process based on mode
            if context.is_single_commit_mode:
                if not context.target_commit_hash:
                    raise ValueError(
                        "Target commit hash missing for single commit CK calculation."
                    )
                commits_to_process_hashes.append(context.target_commit_hash)
                if context.parent_commit_hash:
                    commits_to_process_hashes.append(context.parent_commit_hash)
                else:
                    self._log_warning(
                        context,
                        f"No parent commit hash for target {context.target_commit_hash[:7]}. Only calculating CK for target.",
                    )
                self._log_info(
                    context,
                    f"Calculating CK metrics for specific commits: {[h[:7] for h in commits_to_process_hashes]}",
                )
            else:
                # Full History Mode
                self._log_info(
                    context, "Starting CK metric calculation for repository history..."
                )
                default_branch_ref = git_service.determine_default_branch()
                local_branch_name = default_branch_ref.split("/")[-1]
                self._log_info(
                    context,
                    f"Identified default branch for CK: {local_branch_name} ({default_branch_ref})",
                )
                # Get all commit hashes (consider --first-parent if desired)
                commits_iterator = context.repo_object.iter_commits(
                    rev=default_branch_ref
                )  # Remove first_parent=True to get all
                commits_to_process_hashes = [c.hexsha for c in commits_iterator]
                self._log_info(
                    context,
                    f"Found {len(commits_to_process_hashes)} commits for CK analysis.",
                )

            total_commits_for_ck = len(commits_to_process_hashes)
            self._update_progress(
                context,
                f"Starting CK analysis for {total_commits_for_ck} commits...",
                0,
            )

            # Iterate through the determined commit hashes
            for i, commit_hash in enumerate(commits_to_process_hashes):
                step_progress = (
                    int(80 * ((i + 1) / total_commits_for_ck))
                    if total_commits_for_ck
                    else 0
                )
                self._update_progress(
                    context,
                    f"Calculating CK ({i+1}/{total_commits_for_ck} - {commit_hash[:7]})...",
                    step_progress,
                )
                self._log_info(context, f"Running CK for commit {commit_hash[:7]}...")

                if not git_service.checkout_commit(commit_hash, force=True):
                    self._log_warning(
                        context,
                        f"Failed checkout for commit {commit_hash[:7]}, skipping CK.",
                    )
                    continue

                # --- DB Check Optimization ---
                # The PersistCKMetricsStep already uses UPSERT, so it implicitly handles cases where metrics already exist, preventing duplicates.
                # The optimization here is skipping the expensive CK tool execution if data is already present.
                metrics_exist = False
                if (
                    context.is_single_commit_mode
                ):  # Only check DB in inference mode for now
                    try:
                        metrics_exist = ck_repo.check_metrics_exist_for_commit(
                            context.repository_id, commit_hash
                        )
                    except Exception as db_check_err:
                        self._log_warning(
                            context,
                            f"Failed to check DB for existing CK metrics for {commit_hash[:7]}: {db_check_err}. Will attempt calculation.",
                        )

                if metrics_exist:
                    self._log_info(
                        context,
                        f"CK metrics already exist in DB for {commit_hash[:7]}. Skipping calculation.",
                    )
                    # Optionally, load existing metrics into context if needed by later steps?
                    # For inference, we just need to know they *exist* for PersistCK step to potentially skip.
                    # If CombineFeatures was still here, we would load them.
                    # context.raw_ck_metrics[commit_hash] = ck_repo.get_metrics_as_payload(context.repository_id, commit_hash) # Example
                    continue  # Skip to next commit

                # --- Calculation (if metrics don't exist or not in single_commit_mode) ---
                self._log_info(
                    context, f"Running CK calculation for commit {commit_hash[:7]}..."
                )

                if not git_service.checkout_commit(commit_hash, force=True):
                    self._log_warning(
                        context,
                        f"Failed checkout for commit {commit_hash[:7]}, skipping CK.",
                    )
                    continue

                # Use injected ck_runner
                metrics_df = ck_runner.run(context.repo_local_path, commit_hash)

                if not metrics_df.empty:
                    ck_payload_list: List[CKMetricPayload] = []
                    # Convert DataFrame rows to Pydantic models
                    for record_dict in metrics_df.to_dict(orient="records"):
                        try:
                            payload = CKMetricPayload(**record_dict)
                            # Add IDs here before storing in context
                            payload.repository_id = context.repository_id
                            payload.commit_hash = commit_hash
                            ck_payload_list.append(payload)
                        except ValidationError as e:
                            self._log_warning(
                                context,
                                f"Validation error creating CKMetricPayload for {commit_hash[:7]}, file {record_dict.get('file')}: {e}. Skipping record.",
                            )
                        except Exception as model_e:
                            self._log_error(
                                context,
                                f"Unexpected error creating CK Pydantic model for {commit_hash[:7]}: {model_e}",
                                exc_info=True,
                            )

                    if ck_payload_list:
                        context.raw_ck_metrics[commit_hash] = ck_payload_list
                        self._log_debug(
                            context,
                            f"Stored {len(ck_payload_list)} CK payloads for {commit_hash[:7]}.",
                        )
                    else:
                        self._log_info(
                            context,
                            f"No valid CK payloads generated from DataFrame for commit {commit_hash[:7]}.",
                        )
                else:
                    self._log_info(
                        context, f"CK yielded no metrics for commit {commit_hash[:7]}."
                    )

        except Exception as e:
            self._log_error(context, f"CK calculation failed: {e}", exc_info=True)
            self._log_warning(context, "CK calculation process failed.")
            # Optionally re-raise

        finally:
            checkout_target = (
                original_head
                or getattr(context.repo_object.heads, local_branch_name, None)
                or "HEAD"
            )
            try:
                self._log_info(
                    context,
                    f"Attempting checkout back to '{str(checkout_target)[:10]}...' after CK.",
                )
                context.repo_object.git.checkout(checkout_target, force=True)
                self._log_info(context, "Checkout back successful.")
            except Exception as checkout_err:
                self._log_error(
                    context,
                    f"CRITICAL: Failed to checkout back after CK calculation: {checkout_err}",
                    exc_info=True,
                )
                # raise RuntimeError("Failed to restore repository state after CK calculation.") from checkout_err

        num_commits_with_metrics = len(context.raw_ck_metrics)
        self._log_info(
            context,
            f"Finished CK processing step. Generated/Found metrics for {num_commits_with_metrics} commits.",
        )
        self._update_progress(
            context, "CK processing finished.", 90
        )  # Update progress description
        return context
