# shared/repositories/ml_feature_repository.py
import logging
from typing import Optional, Callable # Added Callable
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session # Keep Session for type hint
from sqlalchemy import select

# Import the Base Repository
from .base_repository import BaseRepository
# Use DB models and column lists from shared
from shared.db.models import CommitGuruMetric, CKMetric # Keep model import
from shared.db import CK_METRIC_COLUMNS, COMMIT_GURU_METRIC_COLUMNS
from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

# Inherit from BaseRepository AND the specific interface
class MLFeatureRepository(BaseRepository): 
    """
    Retrieves persisted metrics from the DB and calculates features
    (including deltas) needed for ML prediction and explanation.
    """
    # Add __init__ to accept session_factory
    def __init__(self, session_factory: Callable[[], Session]):
        # If BaseRepository requires a model type, we might need to reconsider.
        # For now, assume BaseRepository doesn't strictly need ModelType for session scope.
        super().__init__(session_factory) # Initialize BaseRepository
        logger.debug("MLFeatureRepository initialized.")


    # --- Implement the interface method ---
    def get_features_for_commit(self, repo_id: int, commit_hash: str) -> Optional[pd.DataFrame]:
        """
        Fetches CommitGuru and CK metrics for a specific commit and its parent,
        calculates delta CK metrics, and combines them into a combined DataFrame.
        Uses the session scope provided by BaseRepository.
        """
        logger.info(f"MLFeatureRepo: Fetching features for repo {repo_id}, commit {commit_hash[:7]}...")

        # Use the session scope from BaseRepository
        with self._session_scope() as session:
            # --- 1. Fetch Target CommitGuruMetric ---
            cgm_stmt = select(CommitGuruMetric).where(
                CommitGuruMetric.repository_id == repo_id,
                CommitGuruMetric.commit_hash == commit_hash
            )
            target_cgm = session.execute(cgm_stmt).scalar_one_or_none()

            if not target_cgm:
                logger.error(f"MLFeatureRepo: CommitGuruMetric not found for repo {repo_id}, commit {commit_hash[:7]}.")
                return None # Return None within the session scope

            guru_features = {col: getattr(target_cgm, col, None) for col in COMMIT_GURU_METRIC_COLUMNS}
            # --- Add Commit hash ---
            guru_features['commit_hash'] = target_cgm.commit_hash

            # --- 2. Fetch Target CKMetrics ---
            ckm_target_stmt = select(CKMetric).where(
                CKMetric.repository_id == repo_id,
                CKMetric.commit_hash == commit_hash
            )
            target_ck_results = session.execute(ckm_target_stmt).scalars().all()

            if not target_ck_results:
                logger.error(f"MLFeatureRepo: No CKMetric records found for target commit {commit_hash[:7]}. Cannot generate features requiring CK/delta.")
                return None # Return None within the session scope

            target_ck_list = []
            for m in target_ck_results:
                record = {col: getattr(m, col, None) for col in CK_METRIC_COLUMNS}
                record['merge_key_file'] = m.file
                record['merge_key_class'] = m.class_name
                record['class'] = m.class_name
                record['type'] = m.type_
                target_ck_list.append(record)
            target_ck_df = pd.DataFrame(target_ck_list)

            # --- 3. Find Parent Commit Hash ---
            parent_hashes_str = target_cgm.parent_hashes
            if not parent_hashes_str:
                logger.error(f"MLFeatureRepo: Commit {commit_hash[:7]} has no parent hash. Cannot calculate delta features.")
                return None
            parent_hash = parent_hashes_str.split()[0]
            logger.info(f"MLFeatureRepo: Identified parent commit: {parent_hash[:7]}")

            # --- 4. Fetch Parent CKMetrics ---
            ckm_parent_stmt = select(CKMetric).where(
                CKMetric.repository_id == repo_id,
                CKMetric.commit_hash == parent_hash
            )
            parent_ck_results = session.execute(ckm_parent_stmt).scalars().all()
            parent_ck_df = pd.DataFrame()
            if not parent_ck_results:
                logger.warning(f"MLFeatureRepo: No CKMetric records found for parent commit {parent_hash[:7]}. Delta features will be NaN.")
            else:
                parent_ck_list = []
                for m in parent_ck_results:
                    record = {col: getattr(m, col, None) for col in CK_METRIC_COLUMNS}
                    record['merge_key_file'] = m.file
                    record['merge_key_class'] = m.class_name
                    parent_ck_list.append(record)
                parent_ck_df = pd.DataFrame(parent_ck_list)

        # --- Steps 5-8 (Merge, Delta Calc, Combine, Cleanup) happen outside the session scope ---
        # --- These are DataFrame operations ---

        # --- 5. Merge Target and Parent CK DataFrames ---
        if not parent_ck_df.empty:
            parent_ck_df_renamed = parent_ck_df.rename(
                columns={col: f"parent_{col}" for col in CK_METRIC_COLUMNS}
            )
            # Use suffixes=('', '_parent') to avoid modifying already renamed cols
            merged_df = pd.merge(
                target_ck_df, parent_ck_df_renamed,
                on=['merge_key_file', 'merge_key_class'],
                how='left', suffixes=('', '_parent_dup')
            )
            # Drop duplicate parent columns if merge created them (shouldn't with rename)
            merged_df = merged_df[[c for c in merged_df.columns if not c.endswith('_parent_dup')]]

        else:
            merged_df = target_ck_df.copy()
            for col in CK_METRIC_COLUMNS:
                merged_df[f"parent_{col}"] = np.nan

        # --- 6. Calculate Delta Metrics ---
        logger.debug("MLFeatureRepo: Calculating delta metrics...")
        for col in CK_METRIC_COLUMNS:
            current_col = col
            parent_col = f"parent_{col}"
            delta_col = f"d_{col}"

            if current_col in merged_df.columns and parent_col in merged_df.columns:
                target_numeric = pd.to_numeric(merged_df[current_col], errors='coerce')
                parent_numeric = pd.to_numeric(merged_df[parent_col], errors='coerce')
                merged_df[delta_col] = target_numeric - parent_numeric
                mask_invalid = target_numeric.isna() | parent_numeric.isna()
                merged_df.loc[mask_invalid, delta_col] = np.nan
            else:
                merged_df[delta_col] = np.nan

        # --- 7. Combine with CommitGuru Metrics ---
        logger.debug("MLFeatureRepo: Combining CK/Delta with CommitGuru features...")
        final_features_list = []
        for _, row in merged_df.iterrows():
            # Ensure guru_features is defined (fetched within session scope)
            if guru_features is None: # Should not happen if target_cgm was found
                logger.error("MLFeatureRepo: CommitGuru features missing during final combination.")
                return None
            combined_row = {**guru_features, **row.to_dict()}
            final_features_list.append(combined_row)


        if not final_features_list:
             logger.error(f"MLFeatureRepo: Feature generation resulted in empty list for commit {commit_hash[:7]}.")
             return None
        final_df = pd.DataFrame(final_features_list)

        # --- 8. Cleanup ---
        cols_to_drop = [c for c in final_df.columns if c.startswith('parent_') or c.startswith('merge_key_')]
        final_df = final_df.drop(columns=cols_to_drop, errors='ignore')

        logger.info(f"MLFeatureRepo: Finished feature retrieval for commit {commit_hash[:7]}. Shape: {final_df.shape}")
        return final_df # Return the final DataFrame