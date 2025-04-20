# worker/dataset/services/processing_steps.py
import logging
from typing import List, Type

import numpy as np
import pandas as pd
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session, DeclarativeBase

from shared.db.models import BotPattern, CKMetric, PatternTypeEnum, CommitGuruMetric
from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

# Define columns for CK metrics (adjust if CKMetric model attributes change)
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

class ProcessingSteps:
    """Contains static methods for distinct data processing steps."""

    @staticmethod
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

        is_excluded_bot = sa.or_(*exclusion_filters) if exclusion_filters else sa.false()
        is_included_bot = sa.or_(*inclusion_filters) if inclusion_filters else sa.false()

        # A commit IS a bot if it matches any exclusion OR any inclusion (if inclusions exist)
        final_bot_condition = sa.or_(is_excluded_bot, is_included_bot) if inclusion_filters else is_excluded_bot
        return final_bot_condition

    @staticmethod
    def get_parent_ck_metrics(session: Session, current_metrics_batch: pd.DataFrame) -> pd.DataFrame:
        """Fetches parent CK metrics for a batch."""
        if current_metrics_batch.empty:
            parent_cols = ['_parent_metric_found'] + [f"parent_{col}" for col in CK_METRIC_COLUMNS]
            return pd.DataFrame(columns=parent_cols).astype({'_parent_metric_found': bool})

        parent_data_map = {}
        lookup_keys = set()
        batch_map = {}

        for idx, row in current_metrics_batch.iterrows():
            parent_hashes_str = row.get('parent_hashes')
            parent_hash = parent_hashes_str.split()[0] if parent_hashes_str else None
            if parent_hash:
                key = (row['repository_id'], parent_hash, row['file'], row.get('class_name')) # Use .get for class_name
                lookup_keys.add(key)
                if idx not in batch_map: batch_map[idx] = []
                batch_map[idx].append(key)

        if lookup_keys:
            filters = []
            for repo_id, phash, pfile, pclass in lookup_keys:
                 filters.append(
                     sa.and_(
                         CKMetric.repository_id == repo_id,
                         CKMetric.commit_hash == phash,
                         CKMetric.file == pfile,
                         CKMetric.class_name == pclass
                     )
                 )
            if filters:
                parent_stmt = select(CKMetric).where(sa.or_(*filters))
                parent_results = session.execute(parent_stmt).scalars().all()
                for pm in parent_results:
                    key = (pm.repository_id, pm.commit_hash, pm.file, pm.class_name)
                    parent_data_map[key] = {col: getattr(pm, col, None) for col in CK_METRIC_COLUMNS}

        final_data_list = []
        parent_cols_template = {f"parent_{col}": pd.NA for col in CK_METRIC_COLUMNS}

        for idx in current_metrics_batch.index:
            found = False
            parent_metric_data = None
            keys_for_row = batch_map.get(idx, [])
            if keys_for_row:
                 for key in keys_for_row:
                      if key in parent_data_map:
                           parent_metric_data = parent_data_map[key]
                           found = True
                           break
            row_dict = {'_parent_metric_found': found}
            row_dict.update(parent_cols_template) # Start with NAs
            if parent_metric_data:
                 row_dict.update({f"parent_{col}": parent_metric_data.get(col) for col in CK_METRIC_COLUMNS})
            final_data_list.append(row_dict)

        parent_df = pd.DataFrame(final_data_list, index=current_metrics_batch.index)
        if '_parent_metric_found' in parent_df.columns:
             parent_df['_parent_metric_found'] = parent_df['_parent_metric_found'].astype(bool)
        return parent_df

    @staticmethod
    def calculate_delta_metrics(batch_df: pd.DataFrame) -> pd.DataFrame:
        """Calculates d_* metrics."""
        delta_df = batch_df.copy()
        for col in CK_METRIC_COLUMNS:
            current_col = col
            parent_col = f"parent_{col}"
            delta_col = f"d_{col}"
            if current_col in delta_df.columns and parent_col in delta_df.columns:
                current_numeric = pd.to_numeric(delta_df[current_col], errors='coerce')
                parent_numeric = pd.to_numeric(delta_df[parent_col], errors='coerce')
                delta_df[delta_col] = current_numeric - parent_numeric
                # Ensure delta is NaN if parent wasn't found or values were non-numeric
                mask_invalid = ~delta_df['_parent_metric_found'] | current_numeric.isna() | parent_numeric.isna()
                delta_df.loc[mask_invalid, delta_col] = np.nan
            if parent_col in delta_df.columns:
                 delta_df = delta_df.drop(columns=[parent_col])
        return delta_df

    @staticmethod
    def apply_file_filters(batch_df: pd.DataFrame) -> pd.DataFrame:
        """Applies standard file filters (Java, non-test/example/package-info)."""
        logger.debug("Applying file filters...")
        if batch_df.empty or 'file' not in batch_df.columns:
            return batch_df
        initial_len = len(batch_df)
        try:
            is_java = batch_df['file'].str.endswith('.java', na=False)
            is_not_package_info = ~batch_df['file'].str.endswith('package-info.java', na=False)
            file_lower = batch_df['file'].astype(str).str.lower()
            is_not_test = ~file_lower.str.contains("test", na=False)
            is_not_example = ~file_lower.str.contains("example", na=False)
            valid_file_mask = is_java & is_not_package_info & is_not_test & is_not_example
            filtered_df = batch_df[valid_file_mask]
            dropped = initial_len - len(filtered_df)
            if dropped > 0:
                 logger.debug(f"File filters dropped {dropped} rows.")
            return filtered_df
        except Exception as e:
             logger.error(f"Error applying file filters: {e}", exc_info=True)
             return batch_df # Return original on error

    @staticmethod
    def calculate_commit_stats(batch_df: pd.DataFrame) -> pd.DataFrame:
        """Calculates changed_file_count and lines_per_file."""
        logger.debug("Calculating commit stats (changed_file_count, lines_per_file)...")
        if 'files_changed' in batch_df.columns:
            batch_df['changed_file_count'] = batch_df['files_changed'].apply(lambda x: len(x) if isinstance(x, list) else 0)
        else:
            logger.warning("Missing 'files_changed' column, setting 'changed_file_count' to 0.")
            batch_df['changed_file_count'] = 0

        if 'la' in batch_df.columns and 'ld' in batch_df.columns and 'changed_file_count' in batch_df.columns:
             denominator = batch_df['changed_file_count'].replace(0, 1) # Avoid division by zero
             batch_df['lines_per_file'] = (batch_df['la'].fillna(0) + batch_df['ld'].fillna(0)) / denominator
        else:
             logger.warning("Missing 'la', 'ld', or 'changed_file_count', setting 'lines_per_file' to 0.")
             batch_df['lines_per_file'] = 0
        return batch_df

    @staticmethod
    def drop_missing_parents(batch_df: pd.DataFrame) -> pd.DataFrame:
        """Drops rows where the parent metric could not be found."""
        if '_parent_metric_found' in batch_df.columns:
            initial_rows = len(batch_df)
            filtered_df = batch_df[batch_df['_parent_metric_found'] != False]
            dropped = initial_rows - len(filtered_df)
            if dropped > 0:
                 logger.debug(f"Dropped {dropped} rows due to missing parent metrics.")
            return filtered_df
        logger.warning("'_parent_metric_found' column not present, cannot drop missing parents.")
        return batch_df

    @staticmethod
    def select_final_columns(df: pd.DataFrame, feature_columns: List[str], target_column: str) -> pd.DataFrame:
        """Selects the final feature and target columns."""
        # Ensure all feature columns exist
        missing_features = [c for c in feature_columns if c not in df.columns]
        if missing_features:
            logger.error(f"Missing feature columns: {missing_features}")
            raise ValueError(f"Feature columns not found: {missing_features}")
        # Ensure target column exists
        if target_column and target_column not in df.columns:
            logger.error(f"Missing target column: {target_column}")
            raise ValueError(f"Target column '{target_column}' not found in DataFrame.")
        # Select and return
        final_columns = feature_columns + ([target_column] if target_column else [])
        logger.info(f"Selecting final columns: {final_columns}")
        return df[final_columns].copy()