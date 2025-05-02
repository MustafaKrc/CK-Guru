# worker/ml/services/feature_retrieval_service.py
import logging
from typing import Optional, Tuple, List, Dict, Any
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import select

# Use DB models and column lists from shared
from shared.db.models import CommitGuruMetric, CKMetric
from shared.db import CK_METRIC_COLUMNS, COMMIT_GURU_METRIC_COLUMNS
from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

class FeatureRetrievalService:
    """
    Retrieves persisted metrics from the DB and calculates features
    (including deltas) needed for ML prediction and explanation.
    """

    def get_features_for_commit(self, session: Session, repo_id: int, commit_hash: str) -> Optional[pd.DataFrame]:
        """
        Fetches CommitGuru and CK metrics for a specific commit and its parent,
        calculates delta CK metrics, and combines them into a DataFrame suitable
        for ML tasks. Returns None if essential data is missing.
        """
        logger.info(f"FeatureService: Fetching features for repo {repo_id}, commit {commit_hash[:7]}...")

        # --- 1. Fetch Target CommitGuruMetric ---
        cgm_stmt = select(CommitGuruMetric).where(
            CommitGuruMetric.repository_id == repo_id,
            CommitGuruMetric.commit_hash == commit_hash
        )
        target_cgm = session.execute(cgm_stmt).scalar_one_or_none()

        if not target_cgm:
            logger.error(f"FeatureService: CommitGuruMetric not found for repo {repo_id}, commit {commit_hash[:7]}.")
            return None

        guru_features = {col: getattr(target_cgm, col, None) for col in COMMIT_GURU_METRIC_COLUMNS}

        # --- 2. Fetch Target CKMetrics ---
        ckm_target_stmt = select(CKMetric).where(
            CKMetric.repository_id == repo_id,
            CKMetric.commit_hash == commit_hash
        )
        target_ck_results = session.execute(ckm_target_stmt).scalars().all()

        if not target_ck_results:
            logger.error(f"FeatureService: No CKMetric records found for target commit {commit_hash[:7]}. Cannot generate features requiring CK/delta.")
            return None

        target_ck_list = []
        for m in target_ck_results:
            record = {col: getattr(m, col, None) for col in CK_METRIC_COLUMNS}
            record['merge_key_file'] = m.file
            record['merge_key_class'] = m.class_name
            target_ck_list.append(record)
        target_ck_df = pd.DataFrame(target_ck_list)

        # --- 3. Find Parent Commit Hash ---
        parent_hashes_str = target_cgm.parent_hashes
        if not parent_hashes_str:
            logger.error(f"FeatureService: Commit {commit_hash[:7]} has no parent hash. Cannot calculate delta features.")
            # Depending on the model, maybe we can proceed without deltas?
            # For now, return None if deltas are essential.
            return None
        parent_hash = parent_hashes_str.split()[0]
        logger.info(f"FeatureService: Identified parent commit: {parent_hash[:7]}")

        # --- 4. Fetch Parent CKMetrics ---
        ckm_parent_stmt = select(CKMetric).where(
            CKMetric.repository_id == repo_id,
            CKMetric.commit_hash == parent_hash
        )
        parent_ck_results = session.execute(ckm_parent_stmt).scalars().all()
        parent_ck_df = pd.DataFrame()
        if not parent_ck_results:
            logger.warning(f"FeatureService: No CKMetric records found for parent commit {parent_hash[:7]}. Delta features will be NaN.")
        else:
            parent_ck_list = []
            for m in parent_ck_results:
                record = {col: getattr(m, col, None) for col in CK_METRIC_COLUMNS}
                record['merge_key_file'] = m.file
                record['merge_key_class'] = m.class_name
                parent_ck_list.append(record)
            parent_ck_df = pd.DataFrame(parent_ck_list)

        # --- 5. Merge Target and Parent CK DataFrames ---
        if not parent_ck_df.empty:
            parent_ck_df_renamed = parent_ck_df.rename(
                columns={col: f"parent_{col}" for col in CK_METRIC_COLUMNS}
            )
            merged_df = pd.merge(
                target_ck_df, parent_ck_df_renamed,
                on=['merge_key_file', 'merge_key_class'],
                how='left', suffixes=('', '_parent')
            )
        else:
            # If no parent data, start with target and add NaN parent columns
            merged_df = target_ck_df.copy()
            for col in CK_METRIC_COLUMNS:
                merged_df[f"parent_{col}"] = np.nan

        # --- 6. Calculate Delta Metrics ---
        logger.debug("FeatureService: Calculating delta metrics...")
        for col in CK_METRIC_COLUMNS:
            target_col, parent_col, delta_col = col, f"parent_{col}", f"d_{col}"
            if target_col in merged_df.columns and parent_col in merged_df.columns:
                target_numeric = pd.to_numeric(merged_df[target_col], errors='coerce')
                parent_numeric = pd.to_numeric(merged_df[parent_col], errors='coerce')
                merged_df[delta_col] = target_numeric - parent_numeric
                mask_invalid = target_numeric.isna() | parent_numeric.isna()
                merged_df.loc[mask_invalid, delta_col] = np.nan
            else:
                 merged_df[delta_col] = np.nan

        # --- 7. Combine with CommitGuru Metrics ---
        logger.debug("FeatureService: Combining CK/Delta with CommitGuru features...")
        final_features_list = []
        for _, row in merged_df.iterrows():
            combined_row = {**guru_features, **row.to_dict()}
            final_features_list.append(combined_row)

        if not final_features_list:
             logger.error(f"FeatureService: Feature generation resulted in empty list for commit {commit_hash[:7]}.")
             return None
        final_df = pd.DataFrame(final_features_list)

        # --- 8. Cleanup ---
        cols_to_drop = [c for c in final_df.columns if c.startswith('parent_') or c.startswith('merge_key_')]
        final_df = final_df.drop(columns=cols_to_drop, errors='ignore')

        logger.info(f"FeatureService: Finished feature retrieval for commit {commit_hash[:7]}. Shape: {final_df.shape}")
        return final_df

# Create an instance for use within the ML worker
feature_retrieval_service = FeatureRetrievalService()