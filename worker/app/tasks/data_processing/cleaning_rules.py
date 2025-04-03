# worker/app/tasks/data_processing/cleaning_rules.py
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

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

def rule0_drop_duplicates(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """
    Rule 0: Exclude duplicate rows based on identifying metric columns.
            Default subset: commit_hash, file, class_name.
    """
    initial_len = df.shape[0]
    # Define the columns that uniquely identify a metric reading instance
    # Exclude list/dict columns like 'files_changed', 'fixing_commit_hashes'
    subset_cols = DEFAULT_X_COLUMNS + DEFAULT_Y_COLUMN
    # Ensure the subset columns actually exist in the DataFrame
    valid_subset = [col for col in subset_cols if col in df.columns]

    if not valid_subset:
        logger.warning("Rule 0 skipped: Could not find any subset columns DEFAULT_X_COLUMNS + DEFAULT_Y_COLUMN to check for duplicates.")
        return df

    try:
        df_clean = df.drop_duplicates(subset=valid_subset) # Use the subset
        dropped = initial_len - df_clean.shape[0]
        if dropped > 0:
            logger.debug(f"Rule 0: Dropped {dropped} duplicate rows based on subset: {valid_subset}.")
        return df_clean
    except KeyError as e:
         logger.error(f"Rule 0 failed: Column specified in subset not found: {e}. Available columns: {df.columns.tolist()}")
         return df # Return original df on error
    except TypeError as e:
         logger.error(f"Rule 0 failed: Potentially unhashable type still present in subset {valid_subset}? Error: {e}")
         # If this still happens, inspect dtypes of subset columns
         logger.error(f"Dtypes of subset columns: {df[valid_subset].dtypes}")
         return df

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

def rule2_remove_recent_clean_last_change(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """
    Rule 2: Exclude clean changes if they are the last for a class within the batch
            and occurred recently relative to the batch's max time.
    NOTE: This is an adaptation for batch processing and less accurate than the original.
    """
    gap = params.get('gap_seconds', 2419200) # Default 4 weeks
    initial_len = df.shape[0]
    indices_to_drop = []

    if df.empty or 'class_name' not in df.columns or 'author_date_unix_timestamp' not in df.columns or 'is_buggy' not in df.columns:
        logger.warning("Rule 2 skipped: Missing required columns (class_name, author_date_unix_timestamp, is_buggy).")
        return df

    batch_last_time = df['author_date_unix_timestamp'].max()

    # We can only reliably find the 'last change' within the current batch.
    for cls, group in df.groupby('class_name'):
        if group.empty: continue
        group_sorted = group.sort_values('author_date_unix_timestamp', ascending=False) # Sort descending
        last_idx = group_sorted.index[0] # Index of the latest change for this class IN THIS BATCH

        # Check if this latest change (in batch) is clean
        if not df.loc[last_idx, 'is_buggy']: # is_buggy == False means clean
            time_diff = batch_last_time - df.loc[last_idx, 'author_date_unix_timestamp']
            if time_diff < gap:
                indices_to_drop.append(last_idx)

    df_clean = df.drop(index=indices_to_drop)
    dropped = initial_len - df_clean.shape[0]
    if dropped > 0:
        logger.debug(f"Rule 2 (Batch Adapted): Dropped {dropped} rows.")
    return df_clean


def rule3_remove_empty_class(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Rule 3: Exclude rows where totalMethodsQty and totalFieldsQty are both <= 0."""
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

def rule4_remove_trivial_getset(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Rule 4: Heuristic to remove likely getter/setter only classes."""
    initial_len = df.shape[0]
    if {'totalMethodsQty', 'wmc', 'rfc'}.issubset(df.columns):
        # Drop rows where methods exist but complexity is minimal
        mask = ~((df['totalMethodsQty'] > 0) & (df['wmc'].fillna(0) <= 1) & (df['rfc'].fillna(0) <= 1))
        df_clean = df[mask]
        dropped = initial_len - df_clean.shape[0]
        if dropped > 0:
            logger.debug(f"Rule 4: Dropped {dropped} rows.")
        return df_clean
    logger.warning("Rule 4 skipped: Missing required columns.")
    return df

def rule5_remove_no_added_lines(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Rule 5: Exclude rows where la <= 0."""
    initial_len = df.shape[0]
    if 'la' in df.columns:
        mask = df['la'] > 0
        df_clean = df[mask]
        dropped = initial_len - df_clean.shape[0]
        if dropped > 0:
             logger.debug(f"Rule 5: Dropped {dropped} rows.")
        return df_clean
    logger.warning("Rule 5 skipped: Missing 'la' column.")
    return df

def rule6_remove_comment_only_change(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Rule 6: Exclude rows where all d_* metrics are 0."""
    initial_len = df.shape[0]
    d_cols = [col for col in df.columns if col.startswith('d_')]
    if d_cols:
        # Check if all available d_* columns are 0 or NaN
        mask = ~df[d_cols].fillna(0).eq(0).all(axis=1)
        df_clean = df[mask]
        dropped = initial_len - df_clean.shape[0]
        if dropped > 0:
             logger.debug(f"Rule 6: Dropped {dropped} rows.")
        return df_clean
    logger.warning("Rule 6 skipped: No delta (d_*) columns found.")
    return df

def rule7_remove_trivial_method_change(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Rule 7: Exclude minimal line changes that alter method counts."""
    min_change = params.get('min_line_change', 10)
    initial_len = df.shape[0]
    if {'la', 'ld', 'd_totalMethodsQty'}.issubset(df.columns):
        # Exclude if lines changed < min_change AND method count changed
        mask = ~(((df['la'].fillna(0) + df['ld'].fillna(0)) < min_change) & (df['d_totalMethodsQty'].fillna(0) != 0))
        df_clean = df[mask]
        dropped = initial_len - df_clean.shape[0]
        if dropped > 0:
            logger.debug(f"Rule 7: Dropped {dropped} rows.")
        return df_clean
    logger.warning("Rule 7 skipped: Missing required columns.")
    return df

def rule8_remove_type_exception_files(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Rule 8: Exclude changes to *Type.java or *Exception.java files."""
    initial_len = df.shape[0]
    if 'file' in df.columns:
        def file_filter(fname):
            if not isinstance(fname, str) or '.' not in fname:
                return True # Keep if not a typical file string
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

def rule9_remove_dead_code(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Rule 9: Heuristic to remove dead code (CBO=0 and Fan-in=0)."""
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

def rule10_remove_data_class(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Rule 10: Heuristic to remove likely data classes."""
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

def rule11_remove_no_code_change(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Rule 11: Exclude rows where la == 0 and ld == 0."""
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

def rule14_filter_large_commits(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Rule 14: Exclude rows from commits changing more than N files."""
    threshold = params.get('max_files_changed', 10)
    initial_len = df.shape[0]
    if 'changed_file_count' in df.columns and 'is_buggy' in df.columns:
        # Keep rows if file count <= threshold OR if the row is buggy
        mask = (df['changed_file_count'].fillna(0) <= threshold) | (df['is_buggy'] == True)
        df_clean = df[mask]
        dropped = initial_len - df_clean.shape[0]
        if dropped > 0:
            logger.debug(f"Rule 14: Dropped {dropped} rows from non-buggy, large commits (>{threshold} files).")
        return df_clean
    logger.warning("Rule 14 skipped: Missing 'changed_file_count' or 'is_buggy' column.")
    return df


# --- Clustering Rule (incorporating original logic) ---
def rule_cluster_large_commits(df: pd.DataFrame, params: dict, config: Dict[str, Any]) -> pd.DataFrame:
    """
    Rule Cluster: Reduces rows for commits with changed_file_count above a threshold
                  using KMeans clustering and aggregation.
    """
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


# --- Rule Mapping ---
RULE_FUNCTION_MAP = {
    "rule0_drop_duplicates": rule0_drop_duplicates,
    #"rule1_...": rule1_... , # Deferred
    "rule2_remove_recent_clean_last_change": rule2_remove_recent_clean_last_change,
    "rule3_remove_empty_class": rule3_remove_empty_class,
    "rule4_remove_trivial_getset": rule4_remove_trivial_getset,
    "rule5_remove_no_added_lines": rule5_remove_no_added_lines,
    "rule6_remove_comment_only_change": rule6_remove_comment_only_change,
    "rule7_remove_trivial_method_change": rule7_remove_trivial_method_change,
    "rule8_remove_type_exception_files": rule8_remove_type_exception_files,
    "rule9_remove_dead_code": rule9_remove_dead_code,
    "rule10_remove_data_class": rule10_remove_data_class,
    "rule11_remove_no_code_change": rule11_remove_no_code_change,
    # Rule 12/13 (marginal/minimal) - Deferred based on your script's commented out lines? Add if needed.
    "rule14_filter_large_commits": rule14_filter_large_commits,
    "rule_cluster_large_commits": rule_cluster_large_commits,
}