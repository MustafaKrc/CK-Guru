# worker/ingestion/services/steps/calculate_guru.py
import logging
import asyncio
from typing import List

from pydantic import ValidationError

from services.commit_state_tracker import (
    DeveloperExperienceTracker,
    DevExperienceMetrics,
    FileStateTracker,
    FileUpdateResult,
)
from services.git_log_parser import (
    COMMIT_GURU_LOG_FORMAT,
    GitLogParser,
    ParsedNumstatLine,
)
from services.interfaces import IGitService
from services.metric_calculator import CommitMetricsCalculator
from shared.core.config import settings
from shared.schemas.ingestion_data import CommitGuruMetricPayload

from .base import IngestionContext, IngestionStep

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


class CalculateCommitGuruMetricsStep(IngestionStep):
    name = "Calculate Commit Guru Metrics"

    async def execute(
        self, context: IngestionContext, *, git_service: IGitService
    ) -> IngestionContext:
        if not context.repo_local_path or not context.repo_local_path.is_dir():
            msg = "Repository path not valid, cannot calculate metrics."
            self._log_error(context, msg)
            raise ValueError(msg)

        # Instantiate helpers
        parser = GitLogParser()
        file_tracker = FileStateTracker()
        dev_tracker = DeveloperExperienceTracker()
        calculator = CommitMetricsCalculator()

        self._log_info(context, "Starting Commit Guru metric calculation...")

        # Determine log command arguments based on mode
        log_cmd_args = ""  # Only args, 'git ' prefix handled by service
        since_commit = None  # TODO: Add logic if needed
        if context.is_single_commit_mode:
            if not context.parent_commit_hash or not context.target_commit_hash:
                raise ValueError(
                    "Parent or Target commit hash missing for single commit mode."
                )
            log_cmd_args = f"log {context.parent_commit_hash}..{context.target_commit_hash} {COMMIT_GURU_LOG_FORMAT}"
            self._log_info(
                context,
                f"Running git log for range {context.parent_commit_hash[:7]}..{context.target_commit_hash[:7]}",
            )
        elif since_commit:
            log_cmd_args = f"log {since_commit}..HEAD {COMMIT_GURU_LOG_FORMAT}"
            self._log_info(context, f"Running git log since {since_commit}")
        else:
            log_cmd_args = f"log {COMMIT_GURU_LOG_FORMAT}"
            self._log_info(context, "Running git log for full history.")

        try:
            log_output = await asyncio.to_thread(
                git_service.run_git_command, log_cmd_args, True
            )
        except Exception as e:
            self._log_error(
                context, f"Failed to run git log command: {e}", exc_info=True
            )
            raise RuntimeError("Git log command failed") from e

        parsed_commits = parser.parse_custom_log(log_output)
        if not parsed_commits:
            self._log_warning(context, "No commits found in the specified log range.")
            context.raw_commit_guru_data = []
            return context

        final_results_list: List[CommitGuruMetricPayload] = []
        total_parsed = len(parsed_commits)
        await self._update_progress(
            context, f"Processing {total_parsed} parsed commits...", 0
        )

        for i, commit_dict_data in enumerate(parsed_commits):
            commit_hash = commit_dict_data.get("commit_hash")
            author = commit_dict_data.get("author_name")
            timestamp_str = commit_dict_data.get("author_date_unix_timestamp")
            try:
                timestamp = int(timestamp_str) if timestamp_str else 0
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid timestamp '{timestamp_str}' for commit {commit_hash[:7]}. Using 0."
                )
                timestamp = 0
            commit_dict_data["author_date_unix_timestamp"] = (
                timestamp  # Ensure it's int
            )

            numstat_lines_parsed: List[ParsedNumstatLine] = []
            file_update_results_commit: List[FileUpdateResult] = []
            dev_exp_results_commit: List[DevExperienceMetrics] = []
            for line in commit_dict_data.get("stats_lines", []):
                parsed_line = parser.parse_numstat_line(line, commit_hash[:7])
                if parsed_line:
                    numstat_lines_parsed.append(parsed_line)
                    file_update_res = file_tracker.update_file(
                        parsed_line, author, timestamp
                    )
                    dev_exp_res = dev_tracker.update_experience(
                        author, parsed_line.subsystem
                    )
                    file_update_results_commit.append(file_update_res)
                    dev_exp_results_commit.append(dev_exp_res)

            calculated_metrics = calculator.calculate_commit_aggregates(
                numstat_lines_parsed, file_update_results_commit, dev_exp_results_commit
            )
            final_commit_metrics = calculator.finalize_metrics(calculated_metrics)

            # Combine original parsed data with calculated metrics
            final_dict_data = commit_dict_data.copy()
            final_dict_data.pop("stats_lines", None)
            final_dict_data.update(final_commit_metrics)
            final_dict_data["files_changed"] = [
                pnl.file_name for pnl in numstat_lines_parsed
            ] or None

            # Determine 'fix' flag
            commit_message = final_dict_data.get("commit_message", "").lower()
            CORRECTIVE_KEYWORDS = {"fix", "bug", "defect", "error", "patch"}
            final_dict_data["fix"] = any(
                word in commit_message for word in CORRECTIVE_KEYWORDS
            )
            # Ensure timestamp is int
            final_dict_data["author_date_unix_timestamp"] = timestamp

            # --- Instantiate Pydantic Model ---
            try:
                # Pass the combined dictionary to the Pydantic model constructor
                commit_payload = CommitGuruMetricPayload(**final_dict_data)
                final_results_list.append(commit_payload)
            except ValidationError as e:
                self._log_warning(
                    context,
                    f"Validation error creating CommitGuruMetricPayload for {commit_hash[:7]}: {e}. Skipping commit.",
                )
            except Exception as model_e:
                self._log_error(
                    context,
                    f"Unexpected error creating Pydantic model for {commit_hash[:7]}: {model_e}",
                    exc_info=True,
                )

            if (i + 1) % 100 == 0:
                progress = int(95 * ((i + 1) / total_parsed))
                await self._update_progress(
                    context, f"Processed {i+1}/{total_parsed} commits...", progress
                )

        # Store results in context
        context.raw_commit_guru_data = final_results_list

        # Populate maps using the Pydantic objects
        context.commit_hash_to_db_id_map = {}  # Reset map
        context.commit_fix_keyword_map = {}
        for payload in context.raw_commit_guru_data:
            # Access attributes directly from the Pydantic object
            context.commit_hash_to_db_id_map[payload.commit_hash] = -1
            context.commit_fix_keyword_map[payload.commit_hash] = payload.fix

        self._log_info(
            context,
            f"Calculated Commit Guru metrics for {len(context.raw_commit_guru_data)} commits (as Pydantic Payloads).",
        )
        await self._update_progress(context, "Commit Guru calculation complete.", 100)
        return context
