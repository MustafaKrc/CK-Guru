# worker/app/tasks/dataset_generation.py
import logging
from typing import List, Type

import numpy as np
import pandas as pd
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session, DeclarativeBase

from shared.db.models import BotPattern, CKMetric

logger = logging.getLogger(__name__)

# Define columns for CK metrics (adjust if CKMetric model attributes change)
# Note: Use model attribute names (e.g., class_name, type_, lcom_norm)
CK_METRIC_COLUMNS = [
    'file', 'class_name', 'type_', 'cbo', 'cboModified', 'fanin', 'fanout',
    'wmc', 'dit', 'noc', 'rfc', 'lcom', 'lcom_norm', 'tcc', 'lcc',
    'totalMethodsQty', 'staticMethodsQty', 'publicMethodsQty', 'privateMethodsQty',
    'protectedMethodsQty', 'defaultMethodsQty', 'visibleMethodsQty',
    'abstractMethodsQty', 'finalMethodsQty', 'synchronizedMethodsQty',
    'totalFieldsQty', 'staticFieldsQty', 'publicFieldsQty', 'privateFieldsQty',
    'protectedFieldsQty', 'defaultFieldsQty', 'finalFieldsQty',
    'synchronizedFieldsQty', 'nosi', 'loc', 'returnQty', 'loopQty',
    'comparisonsQty', 'tryCatchQty', 'parenthesizedExpsQty',
    'stringLiteralsQty', 'numbersQty', 'assignmentsQty', 'mathOperationsQty',
    'variablesQty', 'maxNestedBlocksQty', 'anonymousClassesQty',
    'innerClassesQty', 'lambdasQty', 'uniqueWordsQty', 'modifiers',
    'logStatementsQty'
]
# Columns from CommitGuruMetric (excluding relationships and JSON fields handled separately)
COMMIT_GURU_METRIC_COLUMNS = [
    'commit_hash', 'parent_hashes', 'author_name', 'author_email', 'author_date',
    'author_date_unix_timestamp', 'commit_message', 'is_buggy', 'fix',
    'files_changed', 'ns', 'nd', 'nf', 'entropy', 'la', 'ld', 'lt', 'ndev',
    'age', 'nuc', 'exp', 'rexp', 'sexp'
]

# --- Helper Functions ---

def get_bot_filter_condition(bot_patterns: List[BotPattern], model_alias: Type[DeclarativeBase]):
    """Builds SQLAlchemy filter conditions for bot authors using an alias."""
    conditions = []
    # Apply exclusions first
    for bp in bot_patterns:
        if bp.is_exclusion:
            # Use the alias provided
            col = getattr(model_alias, 'author_name') # Access attribute via alias
            if bp.pattern_type == 'exact':
                conditions.append(col == bp.pattern)
            elif bp.pattern_type == 'wildcard':
                 sql_pattern = bp.pattern.replace('%', '\\%').replace('_', '\\_').replace('*', '%')
                 conditions.append(col.like(sql_pattern))
            elif bp.pattern_type == 'regex':
                 conditions.append(col.regexp_match(bp.pattern))

    exclusion_condition = sa.or_(*conditions) if conditions else sa.false()

    conditions = []
    # Apply inclusions second
    for bp in bot_patterns:
        if not bp.is_exclusion:
            col = getattr(model_alias, 'author_name') # Use alias
            if bp.pattern_type == 'exact':
                conditions.append(col == bp.pattern)
            elif bp.pattern_type == 'wildcard':
                 sql_pattern = bp.pattern.replace('%', '\\%').replace('_', '\\_').replace('*', '%')
                 conditions.append(col.like(sql_pattern))
            elif bp.pattern_type == 'regex':
                 conditions.append(col.regexp_match(bp.pattern))

    inclusion_condition = sa.or_(*conditions) if conditions else sa.false()

    # Final filter logic remains the same
    if not any(not bp.is_exclusion for bp in bot_patterns):
         final_condition = sa.not_(exclusion_condition)
    else:
         final_condition = sa.not_(exclusion_condition) & inclusion_condition

    return final_condition


def get_parent_ck_metrics(session: Session, current_metrics_batch: pd.DataFrame) -> pd.DataFrame:
    """
    Fetches parent CK metrics for a batch of current metrics.

    Args:
        session: The SQLAlchemy session.
        current_metrics_batch: DataFrame of current CK/CommitGuru metrics,
                               must include 'commit_hash', 'parent_hashes',
                               'repository_id', 'file', 'class_name'.

    Returns:
        DataFrame with parent CK metrics, indexed matching the input batch.
        Parent metrics are prefixed with 'parent_'. Includes '_parent_metric_found' boolean.
    """
    parent_data_map = {} # key: (repo_id, parent_hash, file, class_name), value: ck_metric_dict

    # Prepare lookup keys from the batch
    lookup_keys = set()
    batch_map = {} # Map original index to lookup keys
    for idx, row in current_metrics_batch.iterrows():
        parent_hashes_str = row.get('parent_hashes')
        # Simple approach: use the first parent if multiple exist (merge commit)
        parent_hash = parent_hashes_str.split()[0] if parent_hashes_str else None
        if parent_hash:
            key = (
                row['repository_id'],
                parent_hash,
                row['file'],
                row['class_name'] # Use the correct attribute name
            )
            lookup_keys.add(key)
            if idx not in batch_map: batch_map[idx] = []
            batch_map[idx].append(key) # Store key associated with original index


    if not lookup_keys:
        # Create an empty DataFrame with expected columns if no parents need lookup
        parent_cols = ['_parent_metric_found'] + [f"parent_{col}" for col in CK_METRIC_COLUMNS]
        return pd.DataFrame(columns=parent_cols, index=current_metrics_batch.index)


    # Bulk query for parent metrics using the collected keys
    # This requires crafting a query that can efficiently fetch based on composite keys
    # Using IN operator on tuples might work depending on DB backend support
    # Or construct a more complex OR condition
    # For simplicity here, we might iterate, but a bulk approach is better for performance
    logger.debug(f"Looking up parent metrics for {len(lookup_keys)} unique parent states.")

    # --- Alternative: Bulk query using OR conditions (potentially less optimal than tuple IN) ---
    filters = []
    for repo_id, phash, pfile, pclass in lookup_keys:
         filters.append(
             sa.and_(
                 CKMetric.repository_id == repo_id,
                 CKMetric.commit_hash == phash,
                 CKMetric.file == pfile,
                 CKMetric.class_name == pclass # Use correct attribute name
             )
         )

    if filters:
        parent_stmt = select(CKMetric).where(sa.or_(*filters))
        parent_results = session.execute(parent_stmt).scalars().all()

        # Populate the map
        for pm in parent_results:
            key = (pm.repository_id, pm.commit_hash, pm.file, pm.class_name)
            parent_data_map[key] = {col: getattr(pm, col, None) for col in CK_METRIC_COLUMNS}
        logger.debug(f"Found {len(parent_data_map)} parent metric records in DB.")
    # --- End Bulk Query ---


    # Assemble the result DataFrame
    parent_metrics_list = []
    for idx in current_metrics_batch.index:
        parent_metric = None
        found = False
        # Get the lookup keys associated with this original row
        keys_for_row = batch_map.get(idx, [])
        if keys_for_row:
             # Use the first key found in the map (assumes first parent)
             for key in keys_for_row:
                  if key in parent_data_map:
                       parent_metric = parent_data_map[key]
                       found = True
                       break # Found the first parent

        result_row = {'_parent_metric_found': found}
        if parent_metric:
            result_row.update({f"parent_{col}": parent_metric.get(col) for col in CK_METRIC_COLUMNS})
        else:
            # Fill with NaNs if parent not found
            result_row.update({f"parent_{col}": np.nan for col in CK_METRIC_COLUMNS})
        parent_metrics_list.append(result_row)

    parent_df = pd.DataFrame(parent_metrics_list, index=current_metrics_batch.index)
    return parent_df


def calculate_delta_metrics(batch_df: pd.DataFrame) -> pd.DataFrame:
    """Calculates d_* metrics by subtracting parent metrics from current metrics."""
    delta_df = batch_df.copy() # Start with the merged df (current + parent)

    for col in CK_METRIC_COLUMNS:
        current_col = col
        parent_col = f"parent_{col}"
        delta_col = f"d_{col}"

        if current_col in delta_df.columns and parent_col in delta_df.columns:
            # Ensure columns are numeric, coercing errors to NaN
            current_numeric = pd.to_numeric(delta_df[current_col], errors='coerce')
            parent_numeric = pd.to_numeric(delta_df[parent_col], errors='coerce')

            # Calculate delta only where both values are numeric
            delta_df[delta_col] = current_numeric - parent_numeric
            # Where parent was not found (_parent_metric_found is False), delta should be NaN or current value?
            # Let's make delta NaN if parent was missing or either value was non-numeric
            delta_df.loc[~delta_df['_parent_metric_found'] | current_numeric.isna() | parent_numeric.isna(), delta_col] = np.nan

        # Drop the intermediate parent column
        if parent_col in delta_df.columns:
             delta_df = delta_df.drop(columns=[parent_col])

    return delta_df


