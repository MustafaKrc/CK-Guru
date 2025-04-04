# worker/app/tasks/data_processing/cleaning_rules.py
import logging
from typing import Dict, List, Any, Optional

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from shared.core.config import settings
from shared.cleaning_rules import CleaningRuleBase, RuleParamDefinition, register_rule

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

# Define feature sets (can be passed dynamically later, but useful defaults)
# Keep these aligned with your dataset analysis needs
DEFAULT_X_COLUMNS = [ # Example - adjust based on actual available + delta columns
    "d_cbo","d_cboModified","d_fanin", "d_fanout","d_wmc","d_dit","d_noc",
    "d_rfc","d_lcom", "d_totalMethodsQty","d_staticMethodsQty",
    "d_publicMethodsQty","d_privateMethodsQty","d_protectedMethodsQty",
    "d_defaultMethodsQty","d_visibleMethodsQty","d_abstractMethodsQty",
    "d_finalMethodsQty","d_synchronizedMethodsQty","d_totalFieldsQty",
    "d_staticFieldsQty","d_publicFieldsQty","d_privateFieldsQty",
    "d_protectedFieldsQty","d_defaultFieldsQty","d_finalFieldsQty",
    "d_synchronizedFieldsQty","d_nosi","d_loc","d_returnQty","d_loopQty",
    "d_comparisonsQty","d_tryCatchQty","d_parenthesizedExpsQty",
    "d_stringLiteralsQty", "d_numbersQty","d_assignmentsQty",
    "d_mathOperationsQty","d_variablesQty", "d_maxNestedBlocksQty",
    "d_anonymousClassesQty","d_innerClassesQty", "d_lambdasQty",
    "d_modifiers",
    "cbo","cboModified","fanin","fanout","wmc","dit","noc","rfc","lcom",
    "totalMethodsQty","staticMethodsQty","publicMethodsQty",
    "privateMethodsQty","protectedMethodsQty","defaultMethodsQty",
    "visibleMethodsQty","abstractMethodsQty","finalMethodsQty",
    "synchronizedMethodsQty","totalFieldsQty","staticFieldsQty",
    "publicFieldsQty","privateFieldsQty","protectedFieldsQty",
    "defaultFieldsQty","finalFieldsQty","synchronizedFieldsQty",
    "nosi","loc","returnQty","loopQty","comparisonsQty",
    "tryCatchQty","parenthesizedExpsQty","stringLiteralsQty",
    "numbersQty","assignmentsQty","mathOperationsQty",
    "variablesQty","maxNestedBlocksQty","anonymousClassesQty",
    "innerClassesQty","lambdasQty",
    "modifiers",
    "entropy", # Renamed from entrophy
    "la","ld",
    "lines_per_file", # This needs calculation based on la+ld maybe?
    "changed_file_count",
    # Commit Guru Metrics that might be features
    "ns", "nd", "nf", "ndev", "age", "nuc", "exp", "rexp", "sexp",
]
DEFAULT_Y_COLUMN = ['is_buggy'] # Our target variable name in CommitGuruMetric
DEFAULT_INFO_COLUMNS = [ # Example - adjust as needed
    "class_name", "type", #"linked", "files_changed" (list),
    # Commit Guru info
    "fix", "commit_hash", "file", "author_date_unix_timestamp", "parent_hashes",
    "author_name", "commit_message",
    # Added for clustering/debugging
    "_parent_metric_missing", # Temporary flag
]


# --- Rule Implementations ---

@register_rule
class Rule0DropDuplicates(CleaningRuleBase):
    rule_name = "rule0_drop_duplicates"
    description = "Remove duplicate rows based on identifying metric columns (commit_hash, file, class_name)."
    parameters = []
    is_batch_safe = False # <<< Mark as not safe for pure batch processing

    def apply(self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]) -> pd.DataFrame:
        # This rule should ideally be applied *after* all batches are combined.
        # If applied per-batch, it's less effective. For now, implement per-batch.
        logger.warning("Applying Rule 0 (drop_duplicates) per-batch. Inter-batch duplicates may remain.")
        initial_len = df.shape[0]
        subset_cols = ['commit_hash', 'file', 'class_name']
        valid_subset = [col for col in subset_cols if col in df.columns]

        if not valid_subset:
            logger.warning("Rule 0 skipped: No valid subset columns found.")
            return df
        try:
            # Convert list columns temporarily to tuples if they exist in subset (shouldn't with correct subset)
            # Or better: ensure subset cols are hashable types before drop_duplicates
            df_clean = df.drop_duplicates(subset=valid_subset)
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(f"Rule 0: Dropped {dropped} duplicate rows (within batch).")
            return df_clean
        except Exception as e:
             logger.error(f"Rule 0 failed: {e}. Subset: {valid_subset}. Dtypes: {df[valid_subset].dtypes if valid_subset else 'N/A'}")
             return df # Return original on error

# works poorly..
# def clean_rule_1(df, gap):
#     """
#     Rule 1:
#     Exclude a class change row (c1) if the same class is later deleted (c2) 
#     and the time difference (c2.time - c1.time) is less than the specified gap.
    
#     Assumes:
#       - A column 'class' uniquely identifies a class.
#       - A column 'author_date_unix_timestamp' gives the commit time.
#       - A column 'type' whose value 'deleted' (case-insensitive) indicates deletion.
    
#     Parameters:
#       df  : Input DataFrame.
#       gap : Time gap threshold (same unit as author_date_unix_timestamp).
    
#     Returns:
#       A DataFrame with the rows meeting this rule removed.
#     """
#     df = df.copy()
#     indices_to_drop = []
#     # Process each class separately.
#     for cls, group in df.groupby('class'):
#       group_sorted = group.sort_values('author_date_unix_timestamp')
#       indices = group_sorted.index.tolist()
#       for i in range(len(indices) - 1):
#         c1_idx = indices[i]
#         c2_idx = indices[i + 1]
#         # Convert datetime strings to timestamps for comparison
#         c1_time = pd.to_datetime(df.loc[c1_idx, 'author_date_unix_timestamp']).timestamp()
#         c2_time = pd.to_datetime(df.loc[c2_idx, 'author_date_unix_timestamp']).timestamp()
#         time_diff = c2_time - c1_time
#         # If next commit is a deletion and time difference is too short.
#         if str(df.loc[c2_idx, 'type']).lower() == 'deleted' and time_diff < gap:
#           indices_to_drop.append(c1_idx)

#     print(f"Rule 1: Dropping {len(indices_to_drop)} rows.")

#     return df.drop(index=indices_to_drop)

@register_rule
class Rule2RemoveRecentCleanLastChange(CleaningRuleBase):
    rule_name = "rule2_remove_recent_clean_last_change"
    description = "[Batch Adapted] Exclude clean changes if they are the last for a class within the processing batch and occurred recently relative to the batch's latest commit time. Accuracy may vary."
    parameters = [
        RuleParamDefinition(name="gap_seconds", type="integer", description="Time threshold in seconds.", default=2419200)
    ]
    is_batch_safe = False 

    def apply(self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]) -> pd.DataFrame:
        gap = params.get('gap_seconds', 2419200)
        initial_len = df.shape[0]
        indices_to_drop = []

        if df.empty or 'class_name' not in df.columns or 'author_date_unix_timestamp' not in df.columns or 'is_buggy' not in df.columns:
            logger.warning("Rule 2 skipped: Missing required columns (class_name, author_date_unix_timestamp, is_buggy).")
            return df

        batch_last_time = df['author_date_unix_timestamp'].max()
        for cls, group in df.groupby('class_name'):
            if group.empty: continue
            group_sorted = group.sort_values('author_date_unix_timestamp', ascending=False)
            last_idx = group_sorted.index[0]
            if not df.loc[last_idx, 'is_buggy']:
                time_diff = batch_last_time - df.loc[last_idx, 'author_date_unix_timestamp']
                if time_diff < gap:
                    indices_to_drop.append(last_idx)

        df_clean = df.drop(index=indices_to_drop)
        dropped = initial_len - df_clean.shape[0]
        if dropped > 0:
            logger.debug(f"Rule 2 (Batch Adapted): Dropped {dropped} rows.")
        return df_clean


@register_rule
class Rule3RemoveEmptyClass(CleaningRuleBase):
    rule_name = "rule3_remove_empty_class"
    description = "Exclude changes resulting in classes with no local methods or fields."
    parameters = []
    is_batch_safe = True

    def apply(self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]) -> pd.DataFrame:
        # ... (logic from rule3_remove_empty_class function) ...
        initial_len = df.shape[0]
        if {'totalMethodsQty', 'totalFieldsQty'}.issubset(df.columns):
            mask = (df['totalMethodsQty'] > 0) | (df['totalFieldsQty'] > 0)
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                 logger.debug(f"Rule 3: Dropped {dropped} rows.")
            return df_clean
        logger.warning("Rule 3 skipped: Missing required columns.")
        return df

@register_rule
class Rule4RemoveTrivialGetSet(CleaningRuleBase):
    rule_name = "rule4_remove_trivial_getset"
    description = "Exclude changes involving only likely getter/setter methods (low WMC/RFC heuristic)."
    parameters = []
    is_batch_safe = True

    def apply(self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]) -> pd.DataFrame:
        initial_len = df.shape[0]
        if {'totalMethodsQty', 'wmc', 'rfc'}.issubset(df.columns):
            mask = ~((df['totalMethodsQty'] > 0) & (df['wmc'].fillna(0) <= 1) & (df['rfc'].fillna(0) <= 1))
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(f"Rule 4: Dropped {dropped} rows.")
            return df_clean
        logger.warning("Rule 4 skipped: Missing required columns.")
        return df

@register_rule
class Rule5RemoveNoAddedLines(CleaningRuleBase):
    rule_name = "rule5_remove_no_added_lines"
    description = "Exclude changes where no lines were added (la <= 0)."
    parameters = []
    is_batch_safe = True

    def apply(self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]) -> pd.DataFrame:
        initial_len = df.shape[0]
        if 'la' in df.columns:
            mask = df['la'].fillna(0) > 0 # Treat NaN as 0 for filtering
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                 logger.debug(f"Rule 5: Dropped {dropped} rows.")
            return df_clean
        logger.warning("Rule 5 skipped: Missing 'la' column.")
        return df

@register_rule
class Rule6RemoveCommentOnlyChange(CleaningRuleBase):
    rule_name = "rule6_remove_comment_only_change"
    description = "Exclude changes where likely only comments changed (all d_* metrics are 0)."
    parameters = []
    is_batch_safe = True

    def apply(self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]) -> pd.DataFrame:
        initial_len = df.shape[0]
        d_cols = [col for col in df.columns if col.startswith('d_')]
        if d_cols:
            mask = ~df[d_cols].fillna(0).eq(0).all(axis=1)
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                 logger.debug(f"Rule 6: Dropped {dropped} rows.")
            return df_clean
        logger.warning("Rule 6 skipped: No delta (d_*) columns found.")
        return df

@register_rule
class Rule7RemoveTrivialMethodChange(CleaningRuleBase):
    rule_name = "rule7_remove_trivial_method_change"
    description = "Exclude changes with minimal line alterations but changes in method counts."
    parameters = [RuleParamDefinition(name="min_line_change", type="integer", description="Minimum lines added+deleted to be considered non-trivial.", default=10)]
    is_batch_safe = True

    def apply(self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]) -> pd.DataFrame:
        min_change = params.get('min_line_change', 10)
        initial_len = df.shape[0]
        if {'la', 'ld', 'd_totalMethodsQty'}.issubset(df.columns):
            mask = ~(((df['la'].fillna(0) + df['ld'].fillna(0)) < min_change) & (df['d_totalMethodsQty'].fillna(0) != 0))
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(f"Rule 7: Dropped {dropped} rows.")
            return df_clean
        logger.warning("Rule 7 skipped: Missing required columns.")
        return df

@register_rule
class Rule8RemoveTypeExceptionFiles(CleaningRuleBase):
    rule_name = "rule8_remove_type_exception_files"
    description = "Exclude changes to files named like '*Type.java' or '*Exception.java'."
    parameters = []
    is_batch_safe = True

    def apply(self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]) -> pd.DataFrame:
        initial_len = df.shape[0]
        if 'file' in df.columns:
            def file_filter(fname):
                if not isinstance(fname, str) or '.' not in fname: return True
                base = fname.split('.')[0].strip()
                return not (base.endswith("Type") or base.endswith("Exception"))
            mask = df['file'].apply(file_filter)
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(f"Rule 8: Dropped {dropped} rows.")
            return df_clean
        logger.warning("Rule 8 skipped: Missing 'file' column.")
        return df

@register_rule
class Rule9RemoveDeadCode(CleaningRuleBase):
    rule_name = "rule9_remove_dead_code"
    description = "Exclude changes where the resulting class seems unused (CBO=0 and Fan-in=0 heuristic)."
    parameters = []
    is_batch_safe = True

    def apply(self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]) -> pd.DataFrame:
        initial_len = df.shape[0]
        if {'cbo', 'fanin'}.issubset(df.columns):
            mask = ~((df['cbo'].fillna(0) == 0) & (df['fanin'].fillna(0) == 0))
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(f"Rule 9: Dropped {dropped} rows.")
            return df_clean
        logger.warning("Rule 9 skipped: Missing required columns.")
        return df

@register_rule
class Rule10RemoveDataClass(CleaningRuleBase):
    rule_name = "rule10_remove_data_class"
    description = "Exclude changes likely representing simple data classes (low WMC/RFC, non-zero fields)."
    parameters = []
    is_batch_safe = True

    def apply(self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]) -> pd.DataFrame:
        initial_len = df.shape[0]
        if {'wmc', 'rfc', 'totalFieldsQty'}.issubset(df.columns):
            mask = ~((df['wmc'].fillna(0) <= 1) & (df['rfc'].fillna(0) <= 1) & (df['totalFieldsQty'].fillna(0) >= 1))
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(f"Rule 10: Dropped {dropped} rows.")
            return df_clean
        logger.warning("Rule 10 skipped: Missing required columns.")
        return df

@register_rule
class Rule11RemoveNoCodeChange(CleaningRuleBase):
    rule_name = "rule11_remove_no_code_change"
    description = "Exclude changes where no lines were added or deleted (la == 0 and ld == 0)."
    parameters = []
    is_batch_safe = True

    def apply(self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]) -> pd.DataFrame:
        initial_len = df.shape[0]
        if {'la', 'ld'}.issubset(df.columns):
            mask = ~((df['la'].fillna(0) == 0) & (df['ld'].fillna(0) == 0))
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(f"Rule 11: Dropped {dropped} rows.")
            return df_clean
        logger.warning("Rule 11 skipped: Missing 'la' or 'ld' column.")
        return df

@register_rule
class Rule12RemoveMarginalChange(CleaningRuleBase):
    rule_name = "rule12_remove_marginal_change"
    description = "Exclude non-buggy changes if the sum of absolute delta metrics is too marginal (<= threshold)."
    parameters = [RuleParamDefinition(name="threshold", type="integer", description="Maximum allowed sum of absolute d_* values for non-buggy changes.", default=15)]
    is_batch_safe = True

    def apply(self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]) -> pd.DataFrame:
        threshold = params.get('threshold', 15)
        initial_len = df.shape[0]
        d_cols = [col for col in df.columns if col.startswith('d_')]

        if d_cols and 'is_buggy' in df.columns:
            # Calculate sum, filling NaNs in d_cols with 0 for the sum calculation
            total_change = df[d_cols].fillna(0).abs().sum(axis=1)
            # Keep rows where change > threshold OR the row is buggy
            mask = (total_change > threshold) | (df['is_buggy'] == True)
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(f"Rule 12: Dropped {dropped} non-buggy rows with marginal delta sum <= {threshold}.")
            return df_clean
        logger.warning("Rule 12 skipped: Missing delta (d_*) columns or 'is_buggy' column.")
        return df

@register_rule
class Rule13RemoveMinimalChange(CleaningRuleBase):
    rule_name = "rule13_remove_minimal_change"
    description = "Exclude non-buggy changes if the sum of absolute delta metrics is too minimal (< threshold)."
    parameters = [RuleParamDefinition(name="threshold", type="integer", description="Minimum required sum of absolute d_* values for non-buggy changes.", default=5)]
    is_batch_safe = True

    def apply(self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]) -> pd.DataFrame:
        threshold = params.get('threshold', 5)
        initial_len = df.shape[0]
        d_cols = [col for col in df.columns if col.startswith('d_')]

        if d_cols and 'is_buggy' in df.columns:
            # Calculate sum, filling NaNs in d_cols with 0 for the sum calculation
            total_change = df[d_cols].fillna(0).abs().sum(axis=1)
            # Keep rows where change >= threshold OR the row is buggy
            mask = (total_change >= threshold) | (df['is_buggy'] == True)
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                 logger.debug(f"Rule 13: Dropped {dropped} non-buggy rows with minimal delta sum < {threshold}.") # Corrected log message
            return df_clean
        logger.warning("Rule 13 skipped: Missing delta (d_*) columns or 'is_buggy' column.")
        return df

@register_rule
class Rule14FilterLargeCommits(CleaningRuleBase):
    rule_name = "rule14_filter_large_commits"
    description = "Exclude rows from non-buggy commits that changed more than N files (applied before clustering)."
    parameters = [RuleParamDefinition(name="max_files_changed", type="integer", description="Maximum number of files changed in a non-buggy commit for its rows to be included.", default=10)]
    is_batch_safe = True

    def apply(self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]) -> pd.DataFrame:
        threshold = params.get('max_files_changed', 10)
        initial_len = df.shape[0]
        if 'changed_file_count' in df.columns and 'is_buggy' in df.columns:
            mask = (df['changed_file_count'].fillna(0) <= threshold) | (df['is_buggy'] == True)
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(f"Rule 14: Dropped {dropped} non-buggy rows from large commits (>{threshold} files).")
            return df_clean
        logger.warning("Rule 14 skipped: Missing 'changed_file_count' or 'is_buggy' column.")
        return df


# --- Rule Cluster ---
@register_rule
class RuleClusterLargeCommits(CleaningRuleBase):
    rule_name = "rule_cluster_large_commits"
    description = "Cluster rows within commits changing > N files, reducing rows via aggregation."
    parameters = [
        RuleParamDefinition(name="threshold", type="integer", description="File count threshold to trigger clustering.", default=10)
    ]
    is_batch_safe = False # Assuming commits are split across batches

    def apply(self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]) -> pd.DataFrame:
        threshold = params.get('threshold', 10)
        commit_hash_col = 'commit_hash' # Assuming this column exists

        if 'changed_file_count' not in df.columns or commit_hash_col not in df.columns:
            logger.warning("Rule Cluster skipped: Missing 'changed_file_count' or 'commit_hash' columns.")
            return df

        initial_len = df.shape[0]

        # Get feature/info/target columns from the dataset config if available
        x_columns = config.get('feature_columns', DEFAULT_X_COLUMNS)
        # INFO_COLUMNS might not be explicitly stored, derive if needed or use defaults
        info_columns = DEFAULT_INFO_COLUMNS
        y_column_name = config.get('target_column', DEFAULT_Y_COLUMN[0]) # Assuming single target

        # Ensure target column is in a list for consistency
        y_column = [y_column_name] if isinstance(y_column_name, str) else y_column_name

        # Split data
        df_below = df[df['changed_file_count'] <= threshold].copy() # Use copy to avoid SettingWithCopyWarning
        df_above = df[df['changed_file_count'] > threshold].copy()

        if df_above.empty:
            return df_below # No clustering needed

        # Calculate target number of clusters (avg count below threshold)
        if not df_below.empty:
            # Exclude potential NaNs before calculating mean
            avg_count = int(round(df_below['changed_file_count'].dropna().mean()))
        else:
            avg_count = 1
        avg_count = max(avg_count, 1)
        logger.debug(f"Rule Cluster: Target clusters per large commit: {avg_count}")

        # Define features for clustering (use X columns, remove non-numerics if needed)
        # Filter x_columns to only those present in the DataFrame
        available_x_columns = [col for col in x_columns if col in df.columns]
        # Select only numeric columns among the available features for clustering
        cluster_features = df[available_x_columns].select_dtypes(include=np.number).columns.tolist()

        if not cluster_features:
            logger.warning("Rule Cluster skipped: No numeric features available for clustering.")
            return df # Cannot cluster without numeric features

        reduced_rows_list = [df_below] # Start with the rows below threshold

        # Process each large commit
        for commit, group in df_above.groupby(commit_hash_col):
            if group.shape[0] <= avg_count:
                reduced_rows_list.append(group) # Keep if already small enough
                continue

            # Prepare data for clustering (handle NaNs - fill with mean/median?)
            group_for_cluster = group.copy() # Work on a copy
            # Fill NaNs in numeric clustering features with the mean of that feature *within the commit group*
            for feature in cluster_features:
                if group_for_cluster[feature].isnull().any():
                    group_mean = group_for_cluster[feature].mean()
                    group_for_cluster[feature].fillna(group_mean, inplace=True)
                    # If still NaN (e.g., all values were NaN), fill with 0
                    group_for_cluster[feature].fillna(0, inplace=True)

            # Perform clustering
            try:
                # Use init='k-means++' and n_init='auto' for better robustness
                kmeans = KMeans(n_clusters=avg_count, random_state=42, n_init='auto', init='k-means++')
                clusters = kmeans.fit_predict(group_for_cluster[cluster_features])
                group_for_cluster['cluster'] = clusters
            except Exception as e:
                logger.error(f"Rule Cluster: Clustering failed for commit {commit[:7]}: {e}. Keeping original rows for this commit.")
                reduced_rows_list.append(group) # Keep original group on clustering error
                continue

            # Aggregate by cluster
            agg_funcs = {}
            # Target aggregation: average probability >= 0.5 means True? (adjust as needed)
            def aggregate_target(series):
                # Ensure boolean or becomes float for mean()
                numeric_series = series.astype(float)
                # If mean >= 0.5, classify as buggy (True)
                return numeric_series.mean() >= 0.5

            for col in group_for_cluster.columns:
                if col == 'cluster': continue # Don't aggregate the cluster label itself

                if col == commit_hash_col or col in info_columns:
                    agg_funcs[col] = 'first' # Keep first info value
                elif col in x_columns or col == 'changed_file_count': # Aggregate features + count
                    if pd.api.types.is_numeric_dtype(group_for_cluster[col]):
                        agg_funcs[col] = 'mean' # Average numeric features
                    else:
                        agg_funcs[col] = 'first' # Keep first for non-numeric features
                elif col in y_column:
                    agg_funcs[col] = aggregate_target # Custom aggregation for boolean target
                else: # Default aggregation for other columns
                    if pd.api.types.is_numeric_dtype(group_for_cluster[col]):
                        agg_funcs[col] = 'mean'
                    else:
                        agg_funcs[col] = 'first'

            try:
                aggregated = group_for_cluster.groupby('cluster').agg(agg_funcs).reset_index(drop=True)
                reduced_rows_list.append(aggregated)
            except Exception as agg_e:
                logger.error(f"Rule Cluster: Aggregation failed for commit {commit[:7]} after clustering: {agg_e}. Keeping original rows.")
                reduced_rows_list.append(group) # Keep original group on aggregation error


        # Combine results
        if not reduced_rows_list:
            result_df = pd.DataFrame(columns=df.columns) # Handle case where everything gets filtered?
        else:
            result_df = pd.concat(reduced_rows_list, ignore_index=True, sort=False)

        dropped = initial_len - result_df.shape[0]
        if dropped > 0:
            logger.debug(f"Rule Cluster: Reduced rows by {dropped} via clustering.")
        return result_df

