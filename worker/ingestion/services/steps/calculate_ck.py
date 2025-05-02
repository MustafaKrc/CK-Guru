# worker/ingestion/services/steps/calculate_ck.py
import logging
from pathlib import Path
from typing import Dict
import pandas as pd
from git import Repo, GitCommandError

from .base import IngestionStep, IngestionContext
from shared.utils.git_utils import determine_default_branch, checkout_commit
from shared.core.config import settings
from services.ck_runner_service import ck_runner_service
logger = logging.getLogger(__name__)
log_level = getattr(settings, 'LOG_LEVEL', 'INFO')
logger.setLevel(log_level.upper())

class CalculateCKMetricsStep(IngestionStep):
    name = "Calculate CK Metrics"

    def execute(self, context: IngestionContext) -> IngestionContext:
        if not context.repo_object:
             self._log_warning(context, "Repository object not available, skipping CK analysis.")
             return context

        context.raw_ck_metrics = {} # Reset results for this run
        original_head = None
        try:
            original_head = context.repo_object.head.commit.hexsha # Store original HEAD position
            self._log_info(context, f"Stored original HEAD: {original_head[:7]}")
        except Exception as head_err:
            self._log_warning(context, f"Could not determine original HEAD: {head_err}. Checkout back might fail.")

        try:
            if context.is_single_commit_mode:
                # --- Single Commit Mode ---
                if not context.target_commit_hash:
                    raise ValueError("Target commit hash missing for single commit CK calculation.")

                commits_to_process = {context.target_commit_hash}
                if context.parent_commit_hash:
                    commits_to_process.add(context.parent_commit_hash)
                else:
                    self._log_warning(context, f"No parent commit hash for target {context.target_commit_hash[:7]}. Only calculating CK for target.")

                self._log_info(context, f"Calculating CK metrics for specific commits: {[h[:7] for h in commits_to_process]}")
                self._update_progress(context, "Calculating CK for target/parent...", 0) # Progress within step

                for i, commit_hash in enumerate(commits_to_process):
                    self._log_info(context, f"Running CK for commit {commit_hash[:7]}...")
                    step_progress = int(90 * ((i+1) / len(commits_to_process)))
                    self._update_progress(context, f"Calculating CK for {commit_hash[:7]}...", step_progress)

                    if not checkout_commit(context.repo_object, commit_hash):
                        self._log_warning(context, f"Failed checkout for commit {commit_hash[:7]}, skipping CK.")
                        continue
                
                    metrics_df = ck_runner_service.run(context.repo_local_path, commit_hash)
                    if not metrics_df.empty:
                        context.raw_ck_metrics[commit_hash] = metrics_df
                    else:
                        self._log_info(context, f"CK yielded no metrics for commit {commit_hash[:7]}.")

                self._log_info(context, f"Finished CK calculation for specified commits. Got results for {len(context.raw_ck_metrics)}.")

            else:
                # --- Full History Mode ---
                self._log_info(context, "Starting CK metric calculation for repository commits...")
                processed_hashes_this_run = set()
                processed_ck_count = 0
                local_branch_name = "unknown_branch"

                # Determine default branch for iteration
                default_branch_ref = determine_default_branch(context.repo_object)
                local_branch_name = default_branch_ref.split('/')[-1]
                self._log_info(context, f"Identified default branch for CK: {local_branch_name} ({default_branch_ref})")

                # Estimate total commits
                total_commits_for_ck = 0
                try:
                     count_output = context.repo_object.git.rev_list('--count', '--first-parent', default_branch_ref)
                     total_commits_for_ck = int(count_output.strip())
                     self._log_info(context, f"Estimated {total_commits_for_ck} commits for CK analysis.")
                except (GitCommandError, ValueError, Exception) as count_err:
                     self._log_warning(context, f"Could not estimate total commits for CK progress: {count_err}.")

                commits_iterator = context.repo_object.iter_commits(rev=default_branch_ref, first_parent=True)
                self._update_progress(context, f"Starting CK analysis for ~{total_commits_for_ck} commits...", 0)

                # Iterate and run CK
                for commit in commits_iterator:
                    commit_hash = commit.hexsha
                    if commit_hash in processed_hashes_this_run: continue
                    processed_hashes_this_run.add(commit_hash)
                    processed_ck_count += 1

                    if not checkout_commit(context.repo_object, commit_hash):
                        self._log_warning(context, f"Failed checkout for commit {commit_hash[:7]}, skipping CK.")
                        continue

                    metrics_df = ck_runner_service.run(context.repo_local_path, commit_hash)
                    if not metrics_df.empty: context.raw_ck_metrics[commit_hash] = metrics_df

                    if total_commits_for_ck > 0 and processed_ck_count % 50 == 0:
                        step_progress = int(80 * (processed_ck_count / total_commits_for_ck))
                        self._update_progress(context, f'Calculating CK ({processed_ck_count}/{total_commits_for_ck})...', step_progress)

                self._log_info(context, f"Finished CK calculation. Found metrics for {len(context.raw_ck_metrics)} commits out of {processed_ck_count} processed.")

        except Exception as e:
            self._log_error(context, f"CK calculation failed: {e}", exc_info=True)
            self._log_warning(context, "CK calculation process failed.")
            # Optionally re-raise if critical
            # raise

        finally:
            # Attempt to checkout back to the original head or default branch
            checkout_target = original_head or getattr(context.repo_object.heads, local_branch_name, None) or 'HEAD'
            try:
                self._log_info(context, f"Attempting checkout back to '{str(checkout_target)[:10]}...' after CK.")
                # Use force=True for robustness
                context.repo_object.git.checkout(checkout_target, force=True)
                self._log_info(context, "Checkout back successful.")
            except Exception as checkout_err:
                 # If checkout fails, the repo state is uncertain for subsequent steps.
                 # This could be critical depending on the pipeline.
                 self._log_error(context, f"CRITICAL: Failed to checkout back after CK calculation: {checkout_err}", exc_info=True)
                 # Consider raising an exception here if subsequent steps rely on a specific repo state
                 # raise RuntimeError("Failed to restore repository state after CK calculation.") from checkout_err

        self._update_progress(context, "CK calculation finished.", 90) # Mark end of calculation part
        return context