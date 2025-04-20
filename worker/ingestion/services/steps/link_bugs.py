# worker/ingestion/services/steps/link_bugs.py
import logging
from typing import Dict, Optional, Set, List

from sqlalchemy import update, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .base import IngestionStep, IngestionContext
from shared.db_session import get_sync_db_session
from shared.db.models import CommitGuruMetric
from shared.utils.commit_guru_utils import GitCommitLinker
from shared.core.config import settings
# Import the helper function from utils.py
from ..utils import _get_earliest_linked_issue_timestamp

logger = logging.getLogger(__name__)
log_level = getattr(settings, 'LOG_LEVEL', 'INFO')
logger.setLevel(log_level.upper())

class LinkBugsStep(IngestionStep):
    name = "Link Bugs"

    def execute(self, context: IngestionContext) -> IngestionContext:
        corrective_info: Dict[str, Optional[int]] = {}

        if not context.commit_hash_to_db_id_map:
             self._log_info(context, "Commit hash map is empty, cannot determine corrective commits.")
             return context

        self._log_info(context, "Preparing data for bug linking (checking keywords and issue timestamps)...")
        self._update_progress(context, "Checking fix keywords and issue links...", 0) # Progress within step

        # Need a DB session to query timestamps
        with get_sync_db_session() as session:
            processed_corrective_count = 0
            total_potential_corrective = sum(1 for is_fix in context.commit_fix_keyword_map.values() if is_fix)
            self._log_info(context, f"Found {total_potential_corrective} potential corrective commits based on keywords.")

            for commit_hash, db_id in context.commit_hash_to_db_id_map.items():
                # Consider only commits that were successfully processed/inserted (db_id != -1)
                # and marked with a fix keyword
                if db_id != -1 and context.commit_fix_keyword_map.get(commit_hash, False):
                    processed_corrective_count += 1
                    # Query timestamp for this commit_id using helper
                    earliest_ts = _get_earliest_linked_issue_timestamp(session, db_id)
                    corrective_info[commit_hash] = earliest_ts
                    if processed_corrective_count % 50 == 0:
                        progress = int(20 * (processed_corrective_count / total_potential_corrective)) if total_potential_corrective else 0
                        self._update_progress(context, f"Checking timestamps ({processed_corrective_count}/{total_potential_corrective})...", progress)

        self._log_info(context, f"Prepared {len(corrective_info)} corrective commits with timestamps for linking.")
        self._update_progress(context, "Running GitCommitLinker...", 20)

        if not corrective_info:
            self._log_info(context, "No corrective commits found, skipping bug linking analysis.")
            return context

        if not context.repo_local_path or not context.repo_local_path.is_dir():
            self._log_warning(context, "Repository path invalid, skipping bug linking analysis.")
            return context

        # Run the linker
        try:
            linker = GitCommitLinker(context.repo_local_path)
            # Assume GitCommitLinker logs internally about its progress
            context.bug_link_map_hash = linker.link_corrective_commits(corrective_info)
            self._log_info(context, f"Bug linking analysis identified {len(context.bug_link_map_hash)} potential bug-introducing commits (by hash).")
            self._update_progress(context, "Bug linking analysis complete. Updating database...", 80)
        except Exception as e:
            self._log_error(context, f"Bug linking analysis failed: {e}", exc_info=True)
            # Decide whether to raise or just add warning and continue
            self._log_warning(context, "Bug linking analysis failed, proceeding without updates.")
            return context # Continue without DB updates

        # Update DB based on context.bug_link_map_hash
        if context.bug_link_map_hash:
             self._log_info(context, "Updating bug flags and fixing hashes in database...")
             bug_introducing_commit_ids: Set[int] = set()
             fixing_commit_map_for_update: Dict[int, List[str]] = {} # Store DB_ID -> [fixing_hashes]

             # Convert hashes to DB IDs using the map from the previous step
             for buggy_hash, fixing_hashes in context.bug_link_map_hash.items():
                 buggy_db_id = context.commit_hash_to_db_id_map.get(buggy_hash, -1)
                 if buggy_db_id != -1:
                     bug_introducing_commit_ids.add(buggy_db_id)
                     # Make sure fixing_hashes is JSON serializable (it should be list of strings)
                     fixing_commit_map_for_update[buggy_db_id] = fixing_hashes
                 else:
                      self._log_warning(context, f"Could not find DB ID for potential buggy commit hash {buggy_hash[:7]}. Cannot update.")

             if bug_introducing_commit_ids:
                 with get_sync_db_session() as session:
                     try:
                         # --- Bulk update 'is_buggy' ---
                         if bug_introducing_commit_ids: # Ensure set is not empty
                            update_buggy_stmt = (
                                update(CommitGuruMetric)
                                .where(CommitGuruMetric.id.in_(list(bug_introducing_commit_ids))) # Pass as list
                                .values(is_buggy=True)
                                .execution_options(synchronize_session=False) # Recommended for bulk updates
                            )
                            session.execute(update_buggy_stmt)
                            self._log_info(context, f"Updated is_buggy=True for {len(bug_introducing_commit_ids)} commits.")

                         # --- Update 'fixing_commit_hashes' individually ---
                         # This is often safer than complex bulk JSON updates
                         updated_fixing_count = 0
                         for buggy_db_id, fixing_hashes in fixing_commit_map_for_update.items():
                              try:
                                  update_fixing_stmt = (
                                      update(CommitGuruMetric)
                                      .where(CommitGuruMetric.id == buggy_db_id)
                                      # Store as a simple JSON object for consistency
                                      .values(fixing_commit_hashes={"hashes": fixing_hashes})
                                      .execution_options(synchronize_session=False)
                                  )
                                  session.execute(update_fixing_stmt)
                                  updated_fixing_count += 1
                              except Exception as ind_update_err:
                                  self._log_error(context, f"Failed to update fixing_commit_hashes for commit ID {buggy_db_id}: {ind_update_err}", exc_info=False)
                                  # Continue with other updates

                         self._log_info(context, f"Updated fixing_commit_hashes for {updated_fixing_count} commits.")
                         session.commit()
                         self._log_info(context, "Database successfully updated with bug link information.")
                     except SQLAlchemyError as db_err:
                          self._log_error(context, f"Failed to update DB with bug links: {db_err}", exc_info=True)
                          session.rollback()
                          self._log_warning(context,"Failed to update DB with bug links.") # Add warning to context
                     except Exception as e:
                          self._log_error(context, f"Unexpected error during bug link DB update: {e}", exc_info=True)
                          session.rollback()
                          self._log_warning(context,"Unexpected error during bug link DB update.")
             else:
                  self._log_info(context, "No bug links found requiring database updates.")

        self._update_progress(context, "Bug linking step complete.", 100) # Step complete progress
        return context