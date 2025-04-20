# worker/ingestion/services/steps/calculate_ck.py
import logging
from pathlib import Path
from typing import Dict
import pandas as pd
from git import Repo, GitCommandError

from .base import IngestionStep, IngestionContext
from shared.utils.git_utils import determine_default_branch, checkout_commit
from shared.core.config import settings
# Import the helper function from utils.py
from ..utils import _run_ck_tool

logger = logging.getLogger(__name__)
log_level = getattr(settings, 'LOG_LEVEL', 'INFO')
logger.setLevel(log_level.upper())

class CalculateCKMetricsStep(IngestionStep):
    name = "Calculate CK Metrics"

    def execute(self, context: IngestionContext) -> IngestionContext:
        if not context.repo_object:
             self._log_warning(context, "Repository object not available, skipping CK analysis.")
             return context

        self._log_info(context, "Starting CK metric calculation for repository commits...")
        context.raw_ck_metrics = {} # Reset results
        processed_hashes_this_run = set() # Avoid redundant processing
        processed_ck_count = 0
        local_branch_name = "unknown_branch" # Default

        try:
            # Determine default branch for iteration
            default_branch_ref = determine_default_branch(context.repo_object)
            local_branch_name = default_branch_ref.split('/')[-1] # Extract local name
            self._log_info(context, f"Identified default branch for CK: {local_branch_name} ({default_branch_ref})")

            # Checkout the branch cleanly before iterating commits
            # This ensures CK runs on the correct tree state
            target_ref = next((ref for ref in context.repo_object.remotes.origin.refs if ref.name == default_branch_ref), None)
            if not target_ref:
                 raise ValueError(f"Could not find target ref {default_branch_ref} in origin.")

            if local_branch_name in context.repo_object.heads:
                 self._log_info(context, f"Checking out existing local branch {local_branch_name}...")
                 context.repo_object.heads[local_branch_name].set_tracking_branch(target_ref).checkout(force=True)
            else:
                 self._log_info(context, f"Creating and checking out local branch {local_branch_name} tracking {default_branch_ref}...")
                 context.repo_object.create_head(local_branch_name, target_ref).set_tracking_branch(target_ref).checkout(force=True)
            self._log_info(context, f"Checked out {local_branch_name} for commit iteration.")

            # Estimate total commits (best effort)
            total_commits_for_ck = 0
            try:
                 self._log_info(context, "Estimating total commits for CK progress...")
                 # Use --first-parent for a potentially more stable/faster count
                 count_output = context.repo_object.git.rev_list('--count', '--first-parent', default_branch_ref)
                 total_commits_for_ck = int(count_output.strip())
                 self._log_info(context, f"Estimated {total_commits_for_ck} commits for CK analysis.")
            except (GitCommandError, ValueError, Exception) as count_err:
                 self._log_warning(context, f"Could not estimate total commits for CK progress: {count_err}. Progress reporting limited.")

            commits_iterator = context.repo_object.iter_commits(rev=default_branch_ref, first_parent=True) # Use first_parent for main line history
            self._update_progress(context, f"Starting CK analysis for ~{total_commits_for_ck} commits...", 0) # Progress within step

            # Iterate and run CK
            for commit in commits_iterator:
                commit_hash = commit.hexsha
                if commit_hash in processed_hashes_this_run:
                    continue
                processed_hashes_this_run.add(commit_hash)
                processed_ck_count += 1

                # Optional optimization: Check if CK metrics exist in DB?
                # Needs DB session - maybe better done in Persist step?

                # logger.info(f"Running CK for commit {commit_hash[:7]} ({processed_ck_count}/{total_commits_for_ck or '?'})...") # Too verbose
                if not checkout_commit(context.repo_object, commit_hash): # Use util
                     self._log_warning(context, f"Failed checkout for commit {commit_hash[:7]}, skipping CK.")
                     continue

                metrics_df = _run_ck_tool(context.repo_local_path, commit_hash) # Use helper from utils

                if not metrics_df.empty:
                    context.raw_ck_metrics[commit_hash] = metrics_df
                # else: self._log_info(context, f"CK yielded no metrics for commit {commit_hash[:7]}.") # Too verbose

                # Update progress periodically
                if total_commits_for_ck > 0 and processed_ck_count % 50 == 0:
                    # Allocate, say, 80% of this step's time for calculation
                    step_progress = int(80 * (processed_ck_count / total_commits_for_ck))
                    self._update_progress(context, f'Calculating CK ({processed_ck_count}/{total_commits_for_ck})...', step_progress)

            self._log_info(context, f"Finished CK calculation. Found metrics for {len(context.raw_ck_metrics)} commits out of {processed_ck_count} processed.")

        except Exception as e:
            self._log_error(context, f"CK calculation failed: {e}", exc_info=True)
            # Decide: Raise or add warning and continue? Add warning for now.
            self._log_warning(context,"CK calculation process failed.")
        finally:
            # Attempt to checkout back to the default branch
            try:
                if local_branch_name != "unknown_branch" and local_branch_name in context.repo_object.heads:
                    self._log_info(context, f"Checking out default branch {local_branch_name} after CK.")
                    context.repo_object.heads[local_branch_name].checkout(force=True)
                else:
                     self._log_warning(context, f"Could not checkout default branch '{local_branch_name}' after CK (might not exist locally).")
            except Exception as checkout_err:
                self._log_warning(context, f"Failed to checkout back to default branch: {checkout_err}")

        self._update_progress(context, "CK calculation finished.", 80) # Mark end of calculation part
        return context
