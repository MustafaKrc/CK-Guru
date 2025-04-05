# worker/app/tasks/dataset_generation.py
import logging
from typing import List, Type

import numpy as np
import pandas as pd
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session, DeclarativeBase

from shared.db.models import BotPattern, CKMetric, PatternTypeEnum
from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

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
    inclusion_filters = []
    exclusion_filters = []
    col = getattr(model_alias, 'author_name') # Get column once

    for bp in bot_patterns:
        filter_expr = None
        if bp.pattern_type == PatternTypeEnum.EXACT:
            filter_expr = (col == bp.pattern)
        elif bp.pattern_type == PatternTypeEnum.WILDCARD:
            sql_pattern = bp.pattern.replace('%', '\\%').replace('_', '\\_').replace('*', '%')
            filter_expr = col.like(sql_pattern)
        elif bp.pattern_type == PatternTypeEnum.REGEX:
            filter_expr = col.regexp_match(bp.pattern)

        if filter_expr is not None:
            if bp.is_exclusion:
                exclusion_filters.append(filter_expr)
            else:
                inclusion_filters.append(filter_expr)

    # Combine exclusions: if any exclusion matches, it's a bot
    is_excluded_bot = sa.or_(*exclusion_filters) if exclusion_filters else sa.false()

    # Combine inclusions: if any inclusion matches, it's a bot
    is_included_bot = sa.or_(*inclusion_filters) if inclusion_filters else sa.false()

    # A commit is by a bot if:
    # 1. It matches any exclusion OR
    # 2. It matches any inclusion (only relevant if inclusion list is not empty)
    # We return the condition that evaluates to TRUE if it IS a bot.
    # If there are inclusions defined, matching an inclusion makes it a bot.
    # If there are *no* inclusions defined, only matching an exclusion makes it a bot.

    if inclusion_filters: # If inclusion rules exist, they define the "bot" set along with exclusions
         final_bot_condition = sa.or_(is_excluded_bot, is_included_bot)
    else: # If no inclusion rules, only exclusions define bots
         final_bot_condition = is_excluded_bot

    return final_bot_condition # Return the condition for "IS a bot"


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

    if current_metrics_batch.empty:
        # Define expected output columns for an empty DataFrame
        parent_cols = ['_parent_metric_found'] + [f"parent_{col}" for col in CK_METRIC_COLUMNS]
        # Create empty DataFrame with correct columns and index type
        return pd.DataFrame(columns=parent_cols).astype({'_parent_metric_found': bool})

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


    if lookup_keys:
        # --- Bulk query using OR conditions (potentially less optimal than tuple IN) ---
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

            for pm in parent_results:
                key = (pm.repository_id, pm.commit_hash, pm.file, pm.class_name)
                # Store only the relevant columns
                parent_data_map[key] = {col: getattr(pm, col, None) for col in CK_METRIC_COLUMNS}
            logger.debug(f"Found {len(parent_data_map)} parent metric records in DB.")
        # --- End Bulk Query ---

    # Assemble the result DataFrame row by row
    final_data_list = []
    parent_cols_template = {f"parent_{col}": pd.NA for col in CK_METRIC_COLUMNS} # Use pd.NA

    for idx in current_metrics_batch.index:
        found = False
        parent_metric_data = None
        keys_for_row = batch_map.get(idx, [])

        if keys_for_row:
             for key in keys_for_row:
                  if key in parent_data_map:
                       parent_metric_data = parent_data_map[key]
                       found = True
                       break # Found the first parent

        # Build the row dictionary for this index
        row_dict = {'_parent_metric_found': found} # <<< Start with the boolean flag
        if parent_metric_data:
             # Add parent metrics if found
             row_dict.update({f"parent_{col}": parent_metric_data.get(col) for col in CK_METRIC_COLUMNS})
        else:
             # Add NA placeholders if not found
             row_dict.update(parent_cols_template)

        final_data_list.append(row_dict)

    # Create DataFrame with appropriate types if possible
    parent_df = pd.DataFrame(final_data_list, index=current_metrics_batch.index)
    # Explicitly cast the boolean column AFTER creation, this is usually safer.
    if '_parent_metric_found' in parent_df.columns:
         parent_df['_parent_metric_found'] = parent_df['_parent_metric_found'].astype(bool)
    # Optionally cast numeric parent columns if needed (pd.NA handles types better than np.nan)
    # for col in CK_METRIC_COLUMNS:
    #      parent_col_name = f"parent_{col}"
    #      if parent_col_name in parent_df.columns:
    #          parent_df[parent_col_name] = pd.to_numeric(parent_df[parent_col_name], errors='ignore') # Use ignore for mixed types

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


