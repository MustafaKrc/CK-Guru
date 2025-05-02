# worker/ingestion/services/steps/calculate_guru.py
import logging
from typing import List
from .base import IngestionStep, IngestionContext
from shared.utils.git_log_parser import GitLogParser, COMMIT_GURU_LOG_FORMAT, ParsedNumstatLine
from shared.utils.commit_state_tracker import DevExperienceMetrics, FileStateTracker, DeveloperExperienceTracker, FileUpdateResult
from shared.utils.metric_calculator import CommitMetricsCalculator
from shared.utils.git_utils import run_git_command
from shared.core.config import settings

logger = logging.getLogger(__name__)
log_level = getattr(settings, 'LOG_LEVEL', 'INFO')
logger.setLevel(log_level.upper())

class CalculateCommitGuruMetricsStep(IngestionStep):
    name = "Calculate Commit Guru Metrics"

    def execute(self, context: IngestionContext) -> IngestionContext:
        if not context.repo_local_path or not context.repo_local_path.is_dir():
             msg = "Repository path not valid, cannot calculate metrics."
             self._log_error(context, msg)
             raise ValueError(msg)

        # Instantiate helpers
        parser = GitLogParser()
        file_tracker = FileStateTracker()
        dev_tracker = DeveloperExperienceTracker()
        calculator = CommitMetricsCalculator()

        self._log_info(context, "Starting Commit Guru metric calculation (Refactored)...")

        # Determine log command based on mode
        cmd = f"git log {COMMIT_GURU_LOG_FORMAT}"
        since_commit = None # TODO: Add logic to get last processed commit if needed for full history mode
        if context.is_single_commit_mode:
            if not context.parent_commit_hash or not context.target_commit_hash:
                 raise ValueError("Parent or Target commit hash missing for single commit mode.")
            # Log range from parent (exclusive) to target (inclusive)
            cmd = f"git log {context.parent_commit_hash}..{context.target_commit_hash} {COMMIT_GURU_LOG_FORMAT}"
            self._log_info(context, f"Running git log for range {context.parent_commit_hash[:7]}..{context.target_commit_hash[:7]}")
        elif since_commit:
             cmd = f"git log {since_commit}..HEAD {COMMIT_GURU_LOG_FORMAT}"
             self._log_info(context, f"Running git log since {since_commit}")
        else:
             self._log_info(context, "Running git log for full history.")

        try:
            log_output = run_git_command(cmd, cwd=context.repo_local_path)
        except Exception as e:
             self._log_error(context, f"Failed to run git log command: {e}", exc_info=True)
             raise RuntimeError("Git log command failed") from e

        parsed_commits = parser.parse_custom_log(log_output)
        if not parsed_commits:
            self._log_warning(context, "No commits found in the specified log range.")
            context.raw_commit_guru_data = []
            return context

        final_results_list = []
        total_parsed = len(parsed_commits)
        self._update_progress(context, f"Processing {total_parsed} parsed commits...", 0)

        for i, commit_data in enumerate(parsed_commits):
            commit_hash = commit_data.get('commit_hash')
            author = commit_data.get('author_name')
            timestamp = int(commit_data.get('author_date_unix_timestamp', 0))

            numstat_lines_parsed: List[ParsedNumstatLine] = []
            file_update_results_commit: List[FileUpdateResult] = []
            dev_exp_results_commit: List[DevExperienceMetrics] = []

            for line in commit_data.get('stats_lines', []):
                parsed_line = parser.parse_numstat_line(line, commit_hash[:7])
                if parsed_line:
                    numstat_lines_parsed.append(parsed_line)
                    # Update state trackers for each file change
                    file_update_res = file_tracker.update_file(parsed_line, author, timestamp)
                    dev_exp_res = dev_tracker.update_experience(author, parsed_line.subsystem)
                    file_update_results_commit.append(file_update_res)
                    dev_exp_results_commit.append(dev_exp_res)

            # Calculate aggregated metrics for *this* commit
            calculated_metrics = calculator.calculate_commit_aggregates(
                numstat_lines_parsed,
                file_update_results_commit,
                dev_exp_results_commit
            )
            final_commit_metrics = calculator.finalize_metrics(calculated_metrics)

            # Combine original parsed data with calculated metrics
            final_data = commit_data.copy()
            final_data.pop('stats_lines', None) # Remove raw lines
            final_data.update(final_commit_metrics)
            final_data['files_changed'] = [pnl.file_name for pnl in numstat_lines_parsed] or None # Store changed files

            # Add simple 'fix' keyword flag
            commit_message = final_data.get('commit_message', '').lower()
            # Use constant if defined elsewhere, e.g., from shared.constants
            CORRECTIVE_KEYWORDS = {'fix', 'bug', 'defect', 'error', 'patch'}
            final_data['fix'] = any(word in commit_message for word in CORRECTIVE_KEYWORDS)
            final_data['author_date_unix_timestamp'] = timestamp # Ensure it's int

            final_results_list.append(final_data)

            if (i + 1) % 100 == 0:
                 progress = int(95 * ((i+1)/total_parsed))
                 self._update_progress(context, f"Processed {i+1}/{total_parsed} commits...", progress)


        # Store results in context
        context.raw_commit_guru_data = final_results_list

        # Populate maps (common logic remains)
        context.commit_hash_to_db_id_map = {} # Reset map
        context.commit_fix_keyword_map = {}
        for commit_data in context.raw_commit_guru_data:
            commit_hash = commit_data.get('commit_hash')
            if commit_hash:
                context.commit_hash_to_db_id_map[commit_hash] = -1
                context.commit_fix_keyword_map[commit_hash] = commit_data.get('fix', False)
            else:
                self._log_warning(context, "Found processed commit data entry with missing hash.")

        self._log_info(context, f"Calculated Commit Guru metrics for {len(context.raw_commit_guru_data)} commits.")
        self._update_progress(context, "Commit Guru calculation complete.", 100)
        return context