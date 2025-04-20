# worker/ingestion/services/steps/calculate_guru.py
import logging
from .base import IngestionStep, IngestionContext
from shared.utils.commit_guru_utils import calculate_commit_guru_metrics
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

        self._log_info(context, "Starting Commit Guru metric calculation...")
        try:
            # Assume calculate_commit_guru_metrics handles logging internally
            # TODO: Add check for last processed commit hash from DB to calculate only new ones?
            context.raw_commit_guru_data = calculate_commit_guru_metrics(context.repo_local_path)

            # Populate preliminary maps
            context.commit_hash_to_db_id_map = {} # Reset map
            context.commit_fix_keyword_map = {}
            for commit_data in context.raw_commit_guru_data:
                 commit_hash = commit_data.get('commit_hash')
                 if commit_hash:
                     context.commit_hash_to_db_id_map[commit_hash] = -1 # Placeholder ID
                     context.commit_fix_keyword_map[commit_hash] = commit_data.get('fix', False)
                 else:
                      self._log_warning(context, "Found raw commit data entry with missing hash.")

            self._log_info(context, f"Calculated Commit Guru metrics for {len(context.raw_commit_guru_data)} commits.")
        except Exception as e:
            self._log_error(context, f"Commit Guru metric calculation failed: {e}", exc_info=True)
            raise # Re-raise critical error
        return context