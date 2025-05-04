# worker/ingestion/services/metric_calculator.py
import logging
import math
import numpy as np
from typing import Dict, List, Optional, Any, Set

from shared.core.config import settings
# Import helper structures if needed (though not strictly necessary here)
from .commit_state_tracker import FileUpdateResult, DevExperienceMetrics
from .git_log_parser import ParsedNumstatLine


logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

class CommitMetricsCalculator:
    """Calculates aggregated commit-level metrics from file/dev changes."""

    def calculate_entropy(self, loc_modified_per_file: List[int], total_loc_modified: int) -> float:
        """Calculates code churn entropy."""
        entropy = 0.0
        if total_loc_modified <= 0: # Handle zero or negative total modification
            return 0.0

        for mod_loc in loc_modified_per_file:
            if mod_loc > 0:
                proportion = mod_loc / total_loc_modified
                try:
                    # Avoid log2(0) or log2(tiny) issues, and invalid proportions
                    if proportion > 1e-9 and proportion <= 1.0:
                       entropy -= proportion * math.log2(proportion)
                except ValueError:
                     logger.warning(f"ValueError during entropy calculation for proportion {proportion}. Skipping term.")
        # Ensure entropy is not negative due to potential floating point issues
        return max(0.0, entropy)


    def calculate_commit_aggregates(
        self,
        numstat_lines: List[ParsedNumstatLine],
        file_update_results: List[FileUpdateResult],
        dev_experience_results: List[DevExperienceMetrics] # Assuming one per changed file for the author
        ) -> Dict[str, float]:
        """
        Calculates aggregated metrics for a single commit.

        Args:
            numstat_lines: Parsed numstat info for files changed in the commit.
            file_update_results: Results from FileStateTracker.update_file for each change.
            dev_experience_results: Results from DeveloperExperienceTracker.update_experience for each change.

        Returns:
            Dictionary containing calculated commit metrics (ns, nd, nf, entropy, etc.).
        """
        if not numstat_lines: # Handle commits with no file changes tracked
             return {
                 'ns': 0.0, 'nd': 0.0, 'nf': 0.0, 'entropy': 0.0, 'la': 0.0,
                 'ld': 0.0, 'lt': 0.0, 'ndev': 0.0, 'age': 0.0, 'nuc': 0.0,
                 'exp': 0.0, 'rexp': 0.0, 'sexp': 0.0
             }

        commit_metrics: Dict[str, float] = {
            'la': 0.0, 'ld': 0.0, 'lt': 0.0, 'ndev': 0.0, 'age': 0.0,
            'nuc': 0.0, 'exp': 0.0, 'rexp': 0.0, 'sexp': 0.0
        }

        total_lt = 0.0
        total_nuc = 0.0
        total_age_days = 0.0
        total_exp = 0.0
        total_rexp = 0.0
        total_sexp = 0.0
        total_loc_modified = 0
        loc_modified_per_file: List[int] = []
        authors_in_commit: Set[str] = set()
        subsystems_in_commit: Set[str] = set()
        directories_in_commit: Set[str] = set()

        files_changed_count = len(numstat_lines)

        # Aggregate from numstat lines
        for line in numstat_lines:
            commit_metrics['la'] += line.la
            commit_metrics['ld'] += line.ld
            loc_in_file = line.la + line.ld
            loc_modified_per_file.append(loc_in_file)
            total_loc_modified += loc_in_file
            subsystems_in_commit.add(line.subsystem)
            directories_in_commit.add(line.directory)

        # Aggregate from file update results
        for file_result in file_update_results:
            total_lt += file_result.previous_loc
            total_nuc += file_result.previous_nuc
            total_age_days += file_result.time_diff_days
            authors_in_commit.update(file_result.authors_involved_before)

        # Aggregate from dev experience results
        for dev_result in dev_experience_results:
            total_exp += dev_result.exp
            total_rexp += dev_result.rexp
            total_sexp += dev_result.sexp

        # Calculate final commit-level metrics
        commit_metrics['nf'] = float(files_changed_count)
        commit_metrics['ns'] = float(len(subsystems_in_commit))
        commit_metrics['nd'] = float(len(directories_in_commit))
        # NDEV is the number of developers who touched the modified files *before* this commit.
        commit_metrics['ndev'] = float(len(authors_in_commit))
        commit_metrics['entropy'] = self.calculate_entropy(loc_modified_per_file, total_loc_modified)

        # Calculate averages (handle division by zero)
        if files_changed_count > 0:
            commit_metrics['lt'] = total_lt / files_changed_count
            commit_metrics['age'] = total_age_days / files_changed_count
            commit_metrics['nuc'] = total_nuc / files_changed_count
            commit_metrics['exp'] = total_exp / files_changed_count
            commit_metrics['rexp'] = total_rexp / files_changed_count # Based on placeholder rexp
            commit_metrics['sexp'] = total_sexp / files_changed_count
        else: # Should not happen if numstat_lines is not empty, but safeguard
            commit_metrics['lt'] = 0.0
            commit_metrics['age'] = 0.0
            commit_metrics['nuc'] = 0.0
            commit_metrics['exp'] = 0.0
            commit_metrics['rexp'] = 0.0
            commit_metrics['sexp'] = 0.0

        return commit_metrics


    def finalize_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Replaces NaN/Inf float values with None for DB compatibility."""
        final_metrics = {}
        for key, value in metrics.items():
            if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                final_metrics[key] = None
            else:
                final_metrics[key] = value
        return final_metrics