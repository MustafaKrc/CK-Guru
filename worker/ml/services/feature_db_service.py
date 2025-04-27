# worker/ml/services/feature_db_service.py
import logging
from typing import Optional, Tuple, List, Dict, Any
import pandas as pd
import numpy as np # Import numpy
from sqlalchemy.orm import Session
from sqlalchemy import select

from shared.db import CK_METRIC_COLUMNS, COMMIT_GURU_METRIC_COLUMNS
from shared.db.models import Dataset, CommitGuruMetric, CKMetric
from shared.core.config import settings
from shared.schemas.enums import DatasetStatusEnum


logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

# --- Keep existing function ---
def get_dataset_status_and_path(session: Session, dataset_id: int) -> Tuple[Optional[DatasetStatusEnum], Optional[str]]:
    logger.debug(f"Fetching status/path for Dataset {dataset_id}.")
    dataset = session.get(Dataset, dataset_id)
    if not dataset:
        logger.warning(f"Dataset {dataset_id} not found in DB.")
        return None, None
    return dataset.status, dataset.storage_path

def get_features_for_commit(session: Session, repo_id: int, commit_hash: str) -> Optional[pd.DataFrame]:
    """
    Fetches CommitGuru and CK metrics for a specific commit and its parent,
    calculates delta CK metrics, and combines them into a DataFrame suitable
    for inference, potentially containing multiple rows (one per class/file).
    """
    logger.info(f"Fetching and preparing features for repo {repo_id}, commit {commit_hash[:7]}...")

    # --- 1. Fetch Target CommitGuruMetric ---
    cgm_stmt = select(CommitGuruMetric).where(
        CommitGuruMetric.repository_id == repo_id,
        CommitGuruMetric.commit_hash == commit_hash
    )
    target_cgm = session.execute(cgm_stmt).scalar_one_or_none()

    if not target_cgm:
        logger.error(f"CommitGuruMetric not found for repo {repo_id}, commit {commit_hash[:7]}. Cannot generate features.")
        return None

    # Extract CommitGuru features (commit-level)
    guru_features = {
        col: getattr(target_cgm, col, None) for col in COMMIT_GURU_METRIC_COLUMNS if hasattr(target_cgm, col)
    }
    # Ensure required Guru metrics are present if needed later? For now, just extract.

    # --- 2. Fetch Target CKMetrics ---
    ckm_target_stmt = select(CKMetric).where(
        CKMetric.repository_id == repo_id,
        CKMetric.commit_hash == commit_hash
    )
    target_ck_results = session.execute(ckm_target_stmt).scalars().all()

    if not target_ck_results:
        # If no CK metrics, can we still infer? Depends on the model.
        # Let's assume CK/delta metrics are essential based on the error.
        logger.error(f"No CKMetric records found for target commit {commit_hash[:7]}. Cannot generate features requiring CK/delta.")
        return None # Return None if CK is required

    # Convert target CK to DataFrame - use actual model attribute names
    target_ck_list = []
    for m in target_ck_results:
        # Map DB columns (like 'class_name') back to potential model feature names ('class'?) if needed,
        # or ensure model was trained with DB names. Assuming model uses DB attribute names for now.
        # Handle special names like class_name, type_, lcom_norm if they are features.
        record = {col: getattr(m, col, None) for col in CK_METRIC_COLUMNS}
        # Add keys for merging
        record['merge_key_file'] = m.file
        record['merge_key_class'] = m.class_name # Use the actual attribute name
        target_ck_list.append(record)
    target_ck_df = pd.DataFrame(target_ck_list)

    # --- 3. Find Parent Commit Hash ---
    parent_hashes_str = target_cgm.parent_hashes
    if not parent_hashes_str:
        logger.error(f"Commit {commit_hash[:7]} has no parent hash recorded. Cannot calculate delta features.")
        return None
    # Handle multiple parents? Assume first parent for now.
    parent_hash = parent_hashes_str.split()[0]
    logger.info(f"Found parent commit hash: {parent_hash[:7]}")

    # --- 4. Fetch Parent CKMetrics ---
    ckm_parent_stmt = select(CKMetric).where(
        CKMetric.repository_id == repo_id,
        CKMetric.commit_hash == parent_hash
    )
    parent_ck_results = session.execute(ckm_parent_stmt).scalars().all()

    parent_ck_df = pd.DataFrame() # Initialize empty DataFrame
    if not parent_ck_results:
        logger.warning(f"No CKMetric records found for parent commit {parent_hash[:7]}. Delta features will be NaN.")
        # Create DataFrame with expected columns but no rows, or just merge with empty?
        # Let's create it with merge keys and NaN values for metric columns
        parent_ck_list = []

    else:
        # Convert parent CK to DataFrame
        parent_ck_list = []
        for m in parent_ck_results:
            record = {col: getattr(m, col, None) for col in CK_METRIC_COLUMNS}
            record['merge_key_file'] = m.file
            record['merge_key_class'] = m.class_name
            parent_ck_list.append(record)
        parent_ck_df = pd.DataFrame(parent_ck_list)


    # --- 5. Merge Target and Parent CK DataFrames ---
    # Prefix parent columns to avoid clashes before merge
    parent_ck_df_renamed = parent_ck_df.rename(
        columns={col: f"parent_{col}" for col in CK_METRIC_COLUMNS}
    )
    # Use outer merge to keep all target rows, filling parent NaNs where no match
    merged_df = pd.merge(
        target_ck_df,
        parent_ck_df_renamed,
        left_on=['merge_key_file', 'merge_key_class'],
        right_on=['parent_file', 'parent_class_name'], # Use renamed parent columns if merge keys were also renamed
        how='left',
        suffixes=('', '_parent_unused') # Suffix for parent merge keys if they weren't renamed properly
    )
    # Drop potentially duplicated merge key columns from the parent side if merge didn't use renamed keys
    # Example if parent_ck_df_renamed didn't rename merge keys:
    # merged_df = merged_df.drop(columns=['merge_key_file_parent_unused', 'merge_key_class_parent_unused'], errors='ignore')


    # --- 6. Calculate Delta Metrics ---
    logger.debug("Calculating delta metrics...")
    for col in CK_METRIC_COLUMNS:
        target_col = col
        parent_col = f"parent_{col}"
        delta_col = f"d_{col}"

        if target_col in merged_df.columns and parent_col in merged_df.columns:
            # Convert to numeric, coercing errors to NaN
            target_numeric = pd.to_numeric(merged_df[target_col], errors='coerce')
            parent_numeric = pd.to_numeric(merged_df[parent_col], errors='coerce')
            # Calculate delta only where both are numeric
            merged_df[delta_col] = target_numeric - parent_numeric
            # Ensure delta is NaN if either target or parent was non-numeric or NaN
            mask_invalid = target_numeric.isna() | parent_numeric.isna()
            merged_df.loc[mask_invalid, delta_col] = np.nan
        elif target_col in merged_df.columns:
            # If parent column doesn't exist (e.g., parent commit had no metrics for this file/class)
            merged_df[delta_col] = np.nan # Delta is undefined
        # If target column doesn't exist (shouldn't happen based on earlier checks), do nothing

    # --- 7. Combine with CommitGuru Metrics ---
    logger.debug("Combining CK/Delta features with CommitGuru features...")
    final_features_list = []
    # Add commit-level guru features to each row (class/file level)
    for _, row in merged_df.iterrows():
        combined_row = {**guru_features, **row.to_dict()}
        final_features_list.append(combined_row)

    if not final_features_list:
         logger.error(f"Feature generation resulted in empty list for commit {commit_hash[:7]}.")
         return None

    final_df = pd.DataFrame(final_features_list)

    # --- 8. Cleanup and Column Selection (Optional - maybe done in prepare_data) ---
    # Drop temporary merge keys and parent_ columns if desired
    columns_to_drop = [col for col in final_df.columns if col.startswith('parent_') or col.startswith('merge_key_')]
    final_df = final_df.drop(columns=columns_to_drop, errors='ignore')

    # Ensure all expected columns exist, filling missing ones with NaN or 0?
    # It's better to let the _prepare_data step in the handler raise the error if columns are missing.

    logger.info(f"Finished feature preparation for commit {commit_hash[:7]}. Final shape: {final_df.shape}")
    return final_df