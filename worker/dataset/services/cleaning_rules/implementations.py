# worker/dataset/services/cleaning_rules/implementations.py
import logging
from typing import Any, Dict

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from shared.core.config import settings

from .base import CleaningRuleBase, RuleParamDefinition, register_rule

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

# --- Rule Implementations (Moved from old cleaning_rules.py) ---
# Keep these aligned with your dataset analysis needs
DEFAULT_X_COLUMNS = [  # Example - adjust based on actual available + delta columns
    "d_cbo",
    "d_cboModified",
    "d_fanin",
    "d_fanout",
    "d_wmc",
    "d_dit",
    "d_noc",
    "d_rfc",
    "d_lcom",
    "d_totalMethodsQty",
    "d_staticMethodsQty",
    "d_publicMethodsQty",
    "d_privateMethodsQty",
    "d_protectedMethodsQty",
    "d_defaultMethodsQty",
    "d_visibleMethodsQty",
    "d_abstractMethodsQty",
    "d_finalMethodsQty",
    "d_synchronizedMethodsQty",
    "d_totalFieldsQty",
    "d_staticFieldsQty",
    "d_publicFieldsQty",
    "d_privateFieldsQty",
    "d_protectedFieldsQty",
    "d_defaultFieldsQty",
    "d_finalFieldsQty",
    "d_synchronizedFieldsQty",
    "d_nosi",
    "d_loc",
    "d_returnQty",
    "d_loopQty",
    "d_comparisonsQty",
    "d_tryCatchQty",
    "d_parenthesizedExpsQty",
    "d_stringLiteralsQty",
    "d_numbersQty",
    "d_assignmentsQty",
    "d_mathOperationsQty",
    "d_variablesQty",
    "d_maxNestedBlocksQty",
    "d_anonymousClassesQty",
    "d_innerClassesQty",
    "d_lambdasQty",
    "d_modifiers",
    "cbo",
    "cboModified",
    "fanin",
    "fanout",
    "wmc",
    "dit",
    "noc",
    "rfc",
    "lcom",
    "totalMethodsQty",
    "staticMethodsQty",
    "publicMethodsQty",
    "privateMethodsQty",
    "protectedMethodsQty",
    "defaultMethodsQty",
    "visibleMethodsQty",
    "abstractMethodsQty",
    "finalMethodsQty",
    "synchronizedMethodsQty",
    "totalFieldsQty",
    "staticFieldsQty",
    "publicFieldsQty",
    "privateFieldsQty",
    "protectedFieldsQty",
    "defaultFieldsQty",
    "finalFieldsQty",
    "synchronizedFieldsQty",
    "nosi",
    "loc",
    "returnQty",
    "loopQty",
    "comparisonsQty",
    "tryCatchQty",
    "parenthesizedExpsQty",
    "stringLiteralsQty",
    "numbersQty",
    "assignmentsQty",
    "mathOperationsQty",
    "variablesQty",
    "maxNestedBlocksQty",
    "anonymousClassesQty",
    "innerClassesQty",
    "lambdasQty",
    "modifiers",
    "entropy",  # Renamed from entrophy
    "la",
    "ld",
    "lines_per_file",  # This needs calculation based on la+ld maybe?
    "changed_file_count",
    # Commit Guru Metrics that might be features
    "ns",
    "nd",
    "nf",
    "ndev",
    "age",
    "nuc",
    "exp",
    "rexp",
    "sexp",
]
DEFAULT_Y_COLUMN = ["is_buggy"]  # Our target variable name in CommitGuruMetric
DEFAULT_INFO_COLUMNS = [  # Example - adjust as needed
    "class_name",
    "type",  # "linked", "files_changed" (list),
    # Commit Guru info
    "fix",
    "commit_hash",
    "file",
    "author_date_unix_timestamp",
    "parent_hashes",
    "author_name",
    "commit_message",
    # Added for clustering/debugging
    "_parent_metric_found",  # Temporary flag
]


@register_rule
class DropDuplicates(CleaningRuleBase):
    rule_name = "drop_duplicates"
    description = "Remove duplicate rows based on identifying metric columns (commit_hash, file, class_name)."
    parameters = []
    # Drop duplicates needs the full context to be truly effective.
    # Applying per-batch is possible but won't catch duplicates across batches.
    is_batch_safe = False  # Mark as not batch-safe

    def apply(
        self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]
    ) -> pd.DataFrame:
        initial_len = df.shape[0]
        subset_cols = ["commit_hash", "file", "class_name"]
        valid_subset = [col for col in subset_cols if col in df.columns]

        if not valid_subset:
            logger.warning(
                "Rule 0 skipped: No valid subset columns found (%s).", subset_cols
            )
            return df
        try:
            df_clean = df.drop_duplicates(
                subset=valid_subset, keep="first"
            )  # Keep first occurence
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(f"Rule 0: Dropped {dropped} duplicate rows.")
            return df_clean
        except TypeError as e:
            # This can happen if a column in the subset is not hashable (e.g., a list)
            logger.error(
                f"Rule 0 failed due to unhashable type in subset {valid_subset}: {e}. Returning original DataFrame.",
                exc_info=True,
            )
            return df
        except Exception as e:
            logger.error(
                f"Rule 0 failed unexpectedly: {e}. Subset: {valid_subset}. Dtypes: {df[valid_subset].dtypes if valid_subset else 'N/A'}",
                exc_info=True,
            )
            return df  # Return original on error


@register_rule
class RemoveRecentCleanLastChange(CleaningRuleBase):
    rule_name = "remove_recent_clean_last_change"
    description = "Exclude clean changes if they are the last for a class and occurred recently."
    parameters = [
        RuleParamDefinition(
            name="gap_seconds",
            type="integer",
            description="Time threshold in seconds.",
            default=2419200,
        )
    ]
    # This rule needs to know the *actual* last change time for a class across the whole dataset.
    is_batch_safe = False

    def apply(
        self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]
    ) -> pd.DataFrame:
        gap = params.get("gap_seconds", 2419200)  # Default: 28 days
        initial_len = df.shape[0]

        required_cols = ["class_name", "author_date_unix_timestamp", "is_buggy"]
        if not all(col in df.columns for col in required_cols):
            logger.warning(
                f"Rule 2 skipped: Missing one or more required columns: {required_cols}."
            )
            return df
        if df.empty:
            return df

        # Find the last timestamp in the entire dataset being processed
        last_overall_time = df["author_date_unix_timestamp"].max()

        # Find the index of the last commit for each class
        # Use transform to get the max timestamp per class aligned with the original df
        df["last_class_time"] = df.groupby("class_name")[
            "author_date_unix_timestamp"
        ].transform("max")

        # Identify rows to drop:
        # 1. It's the last commit for that class (its timestamp matches the max class timestamp)
        # 2. It's clean (not buggy)
        # 3. Its timestamp is recent relative to the overall last timestamp
        mask_is_last_for_class = (
            df["author_date_unix_timestamp"] == df["last_class_time"]
        )
        mask_is_clean = not df["is_buggy"]
        mask_is_recent = (last_overall_time - df["author_date_unix_timestamp"]) < gap

        mask_to_drop = mask_is_last_for_class & mask_is_clean & mask_is_recent

        df_clean = df[~mask_to_drop].drop(
            columns=["last_class_time"]
        )  # Drop the temporary column
        dropped = initial_len - df_clean.shape[0]
        if dropped > 0:
            logger.debug(
                f"Rule 2: Dropped {dropped} recent, clean last changes for classes."
            )
        return df_clean


@register_rule
class RemoveEmptyClass(CleaningRuleBase):
    rule_name = "remove_empty_class"
    description = (
        "Exclude changes resulting in classes with no local methods or fields."
    )
    parameters = []
    is_batch_safe = True  # This rule only looks at individual rows

    def apply(
        self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]
    ) -> pd.DataFrame:
        initial_len = df.shape[0]
        required_cols = ["totalMethodsQty", "totalFieldsQty"]
        if all(col in df.columns for col in required_cols):
            # Keep rows where methods > 0 OR fields > 0 (handle NaN as not > 0)
            mask = (df["totalMethodsQty"].fillna(0) > 0) | (
                df["totalFieldsQty"].fillna(0) > 0
            )
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(
                    f"Rule 3: Dropped {dropped} rows corresponding to empty classes."
                )
            return df_clean
        logger.warning(f"Rule 3 skipped: Missing required columns: {required_cols}.")
        return df


@register_rule
class RemoveTrivialGetSet(CleaningRuleBase):
    rule_name = "remove_trivial_getset"
    description = "Exclude changes involving only likely getter/setter methods (low WMC/RFC heuristic)."
    parameters = []
    is_batch_safe = True  # Looks at individual rows

    def apply(
        self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]
    ) -> pd.DataFrame:
        initial_len = df.shape[0]
        required_cols = ["totalMethodsQty", "wmc", "rfc"]
        if all(col in df.columns for col in required_cols):
            # Keep rows where it's NOT the case that (methods>0 AND wmc<=1 AND rfc<=1)
            # Handle NaNs by filling with 0, so NaN <= 1 evaluates to True
            mask = ~(
                (df["totalMethodsQty"].fillna(0) > 0)
                & (df["wmc"].fillna(0) <= 1)
                & (df["rfc"].fillna(0) <= 1)
            )
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(
                    f"Rule 4: Dropped {dropped} rows likely corresponding to trivial getter/setter classes."
                )
            return df_clean
        logger.warning(f"Rule 4 skipped: Missing required columns: {required_cols}.")
        return df


@register_rule
class RemoveNoAddedLines(CleaningRuleBase):
    rule_name = "remove_no_added_lines"
    description = "Exclude changes where no lines were added (la <= 0)."
    parameters = []
    is_batch_safe = True  # Looks at individual rows

    def apply(
        self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]
    ) -> pd.DataFrame:
        initial_len = df.shape[0]
        if "la" in df.columns:
            mask = df["la"].fillna(0) > 0  # Treat NaN as 0 for filtering
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(
                    f"Rule 5: Dropped {dropped} rows with no lines added (la <= 0)."
                )
            return df_clean
        logger.warning("Rule 5 skipped: Missing 'la' column.")
        return df


@register_rule
class RemoveCommentOnlyChange(CleaningRuleBase):
    rule_name = "remove_comment_only_change"
    description = (
        "Exclude changes where likely only comments changed (all d_* metrics are 0)."
    )
    parameters = []
    is_batch_safe = True  # Looks at individual rows

    def apply(
        self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]
    ) -> pd.DataFrame:
        initial_len = df.shape[0]
        d_cols = [col for col in df.columns if col.startswith("d_")]
        if d_cols:
            # Keep rows where AT LEAST ONE d_* metric is non-zero
            mask = ~df[d_cols].fillna(0).eq(0).all(axis=1)
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(
                    f"Rule 6: Dropped {dropped} rows with only comment changes (all d_* were 0)."
                )
            return df_clean
        logger.warning("Rule 6 skipped: No delta (d_*) columns found.")
        return df


@register_rule
class RemoveTrivialMethodChange(CleaningRuleBase):
    rule_name = "remove_trivial_method_change"
    description = (
        "Exclude changes with minimal line alterations but changes in method counts."
    )
    parameters = [
        RuleParamDefinition(
            name="min_line_change",
            type="integer",
            description="Minimum lines added+deleted to be considered non-trivial.",
            default=10,
        )
    ]
    is_batch_safe = True  # Looks at individual rows

    def apply(
        self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]
    ) -> pd.DataFrame:
        min_change = params.get("min_line_change", 10)
        initial_len = df.shape[0]
        required_cols = ["la", "ld", "d_totalMethodsQty"]
        if all(col in df.columns for col in required_cols):
            # Keep rows where it's NOT the case that (line change < min_change AND method count changed)
            mask = ~(
                ((df["la"].fillna(0) + df["ld"].fillna(0)) < min_change)
                & (df["d_totalMethodsQty"].fillna(0) != 0)
            )
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(
                    f"Rule 7: Dropped {dropped} rows with trivial line changes (<{min_change}) but method count changes."
                )
            return df_clean
        logger.warning(f"Rule 7 skipped: Missing required columns: {required_cols}.")
        return df


@register_rule
class RemoveTypeExceptionFiles(CleaningRuleBase):
    rule_name = "remove_type_exception_files"
    description = (
        "Exclude changes to files named like '*Type.java' or '*Exception.java'."
    )
    parameters = []
    is_batch_safe = True  # Looks at individual rows

    def apply(
        self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]
    ) -> pd.DataFrame:
        initial_len = df.shape[0]
        if "file" in df.columns:
            # Filter keeping rows that DON'T match the patterns
            # Handle potential non-string values in 'file' column
            mask = (
                df["file"]
                .astype(str)
                .str.contains(r"(Type|Exception)\.java$", regex=True, na=False)
            )
            df_clean = df[~mask]  # Keep rows where the mask is False
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(
                    f"Rule 8: Dropped {dropped} rows matching '*Type.java' or '*Exception.java'."
                )
            return df_clean
        logger.warning("Rule 8 skipped: Missing 'file' column.")
        return df


@register_rule
class RemoveDeadCode(CleaningRuleBase):
    rule_name = "remove_dead_code"
    description = "Exclude changes where the resulting class seems unused (CBO=0 and Fan-in=0 heuristic)."
    parameters = []
    is_batch_safe = True  # Looks at individual rows

    def apply(
        self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]
    ) -> pd.DataFrame:
        initial_len = df.shape[0]
        required_cols = ["cbo", "fanin"]
        if all(col in df.columns for col in required_cols):
            # Keep rows where it's NOT the case that (cbo=0 AND fanin=0)
            mask = ~((df["cbo"].fillna(0) == 0) & (df["fanin"].fillna(0) == 0))
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(
                    f"Rule 9: Dropped {dropped} rows likely corresponding to dead code (cbo=0, fanin=0)."
                )
            return df_clean
        logger.warning(f"Rule 9 skipped: Missing required columns: {required_cols}.")
        return df


@register_rule
class RemoveDataClass(CleaningRuleBase):
    rule_name = "remove_data_class"
    description = "Exclude changes likely representing simple data classes (low WMC/RFC, non-zero fields)."
    parameters = []
    is_batch_safe = True  # Looks at individual rows

    def apply(
        self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]
    ) -> pd.DataFrame:
        initial_len = df.shape[0]
        required_cols = ["wmc", "rfc", "totalFieldsQty"]
        if all(col in df.columns for col in required_cols):
            # Keep rows where it's NOT the case that (wmc<=1 AND rfc<=1 AND fields>=1)
            mask = ~(
                (df["wmc"].fillna(0) <= 1)
                & (df["rfc"].fillna(0) <= 1)
                & (df["totalFieldsQty"].fillna(0) >= 1)
            )
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(
                    f"Rule 10: Dropped {dropped} rows likely corresponding to data classes."
                )
            return df_clean
        logger.warning(f"Rule 10 skipped: Missing required columns: {required_cols}.")
        return df


@register_rule
class RemoveNoCodeChange(CleaningRuleBase):
    rule_name = "remove_no_code_change"
    description = (
        "Exclude changes where no lines were added or deleted (la == 0 and ld == 0)."
    )
    parameters = []
    is_batch_safe = True  # Looks at individual rows

    def apply(
        self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]
    ) -> pd.DataFrame:
        initial_len = df.shape[0]
        required_cols = ["la", "ld"]
        if all(col in df.columns for col in required_cols):
            # Keep rows where it's NOT the case that (la=0 AND ld=0)
            mask = ~((df["la"].fillna(0) == 0) & (df["ld"].fillna(0) == 0))
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(
                    f"Rule 11: Dropped {dropped} rows with no lines added or deleted."
                )
            return df_clean
        logger.warning(f"Rule 11 skipped: Missing required columns: {required_cols}.")
        return df


@register_rule
class RemoveMarginalChange(CleaningRuleBase):
    rule_name = "remove_marginal_change"
    description = "Exclude non-buggy changes if the sum of absolute delta metrics is too marginal (<= threshold)."
    parameters = [
        RuleParamDefinition(
            name="threshold",
            type="integer",
            description="Maximum allowed sum of absolute d_* values for non-buggy changes.",
            default=15,
        )
    ]
    is_batch_safe = True  # Looks at individual rows

    def apply(
        self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]
    ) -> pd.DataFrame:
        threshold = params.get("threshold", 15)
        initial_len = df.shape[0]
        d_cols = [col for col in df.columns if col.startswith("d_")]

        if d_cols and "is_buggy" in df.columns:
            total_change = df[d_cols].fillna(0).abs().sum(axis=1)
            # Keep rows where change > threshold OR the row is buggy
            mask = (total_change > threshold) | (df["is_buggy"])
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(
                    f"Rule 12: Dropped {dropped} non-buggy rows with marginal delta sum <= {threshold}."
                )
            return df_clean
        logger.warning(
            "Rule 12 skipped: Missing delta (d_*) columns or 'is_buggy' column."
        )
        return df


@register_rule
class RemoveMinimalChange(CleaningRuleBase):
    rule_name = "remove_minimal_change"
    description = "Exclude non-buggy changes if the sum of absolute delta metrics is too minimal (< threshold)."
    parameters = [
        RuleParamDefinition(
            name="threshold",
            type="integer",
            description="Minimum required sum of absolute d_* values for non-buggy changes.",
            default=5,
        )
    ]
    is_batch_safe = True  # Looks at individual rows

    def apply(
        self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]
    ) -> pd.DataFrame:
        threshold = params.get("threshold", 5)
        initial_len = df.shape[0]
        d_cols = [col for col in df.columns if col.startswith("d_")]

        if d_cols and "is_buggy" in df.columns:
            total_change = df[d_cols].fillna(0).abs().sum(axis=1)
            # Keep rows where change >= threshold OR the row is buggy
            mask = (total_change >= threshold) | (df["is_buggy"])
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(
                    f"Rule 13: Dropped {dropped} non-buggy rows with minimal delta sum < {threshold}."
                )
            return df_clean
        logger.warning(
            "Rule 13 skipped: Missing delta (d_*) columns or 'is_buggy' column."
        )
        return df


@register_rule
class FilterLargeCommits(CleaningRuleBase):
    rule_name = "filter_large_commits"
    description = "Exclude rows from non-buggy commits that changed more than N files (applied before clustering)."
    parameters = [
        RuleParamDefinition(
            name="max_files_changed",
            type="integer",
            description="Maximum number of files changed in a non-buggy commit for its rows to be included.",
            default=10,
        )
    ]
    # This rule can be applied per batch, as it looks at commit-level stats that should be consistent within the batch.
    is_batch_safe = True

    def apply(
        self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]
    ) -> pd.DataFrame:
        threshold = params.get("max_files_changed", 10)
        initial_len = df.shape[0]
        required_cols = ["changed_file_count", "is_buggy"]
        if all(col in df.columns for col in required_cols):
            # Keep rows where file count <= threshold OR the row is buggy
            mask = (df["changed_file_count"].fillna(0) <= threshold) | (df["is_buggy"])
            df_clean = df[mask]
            dropped = initial_len - df_clean.shape[0]
            if dropped > 0:
                logger.debug(
                    f"Rule 14: Dropped {dropped} non-buggy rows from large commits (>{threshold} files)."
                )
            return df_clean
        logger.warning(f"Rule 14 skipped: Missing required columns: {required_cols}.")
        return df


# --- Rule Cluster ---
@register_rule
class ClusterLargeCommits(CleaningRuleBase):
    rule_name = "cluster_large_commits"
    description = "Cluster rows within commits changing > N files, reducing rows via aggregation."
    parameters = [
        RuleParamDefinition(
            name="threshold",
            type="integer",
            description="File count threshold to trigger clustering.",
            default=10,
        )
    ]
    # This rule needs to see all rows for a commit to cluster them, making it non-batch-safe.
    is_batch_safe = False

    def apply(
        self, df: pd.DataFrame, params: Dict[str, Any], config: Dict[str, Any]
    ) -> pd.DataFrame:
        threshold = params.get("threshold", 10)
        commit_hash_col = "commit_hash"

        required_cols = ["changed_file_count", commit_hash_col]
        if not all(col in df.columns for col in required_cols):
            logger.warning(
                f"Rule Cluster skipped: Missing required columns: {required_cols}."
            )
            return df
        if df.empty:
            return df

        initial_len = df.shape[0]

        # Get feature/info/target columns from the dataset config
        x_columns = config.get("feature_columns", DEFAULT_X_COLUMNS)
        info_columns = DEFAULT_INFO_COLUMNS  # Use defaults for now
        y_column_name = config.get("target_column", DEFAULT_Y_COLUMN[0])
        y_column = [y_column_name] if isinstance(y_column_name, str) else y_column_name

        # Split data
        df_below = df[df["changed_file_count"] <= threshold].copy()
        df_above = df[df["changed_file_count"] > threshold].copy()

        if df_above.empty:
            return df_below

        # Calculate target number of clusters
        avg_count = (
            int(round(df_below["changed_file_count"].mean()))
            if not df_below.empty
            else 1
        )
        avg_count = max(avg_count, 1)
        logger.debug(f"Rule Cluster: Target clusters per large commit: {avg_count}")

        available_x_columns = [col for col in x_columns if col in df.columns]
        cluster_features = (
            df[available_x_columns].select_dtypes(include=np.number).columns.tolist()
        )

        if not cluster_features:
            logger.warning(
                "Rule Cluster skipped: No numeric features found for clustering."
            )
            return df  # Return original DataFrame if no features

        reduced_rows_list = [df_below]

        for commit, group in df_above.groupby(commit_hash_col):
            if group.shape[0] <= avg_count:
                reduced_rows_list.append(group)
                continue

            group_for_cluster = group.copy()
            for feature in cluster_features:
                if group_for_cluster[feature].isnull().any():
                    group_mean = group_for_cluster[feature].mean()
                    group_for_cluster[feature].fillna(group_mean, inplace=True)
                    group_for_cluster[feature].fillna(
                        0, inplace=True
                    )  # Fallback if all were NaN

            try:
                n_clusters = min(
                    avg_count, group.shape[0]
                )  # Cannot have more clusters than samples
                if (
                    n_clusters < 1
                ):  # Should not happen if group is not empty, but safeguard
                    logger.warning(
                        f"Rule Cluster: Calculated n_clusters={n_clusters} for commit {commit[:7]}. Skipping clustering for this commit."
                    )
                    reduced_rows_list.append(group)
                    continue

                kmeans = KMeans(
                    n_clusters=n_clusters,
                    random_state=42,
                    n_init="auto",
                    init="k-means++",
                )
                clusters = kmeans.fit_predict(group_for_cluster[cluster_features])
                group_for_cluster["cluster"] = clusters
            except Exception as e:
                logger.error(
                    f"Rule Cluster: Clustering failed for commit {commit[:7]}: {e}. Keeping original rows.",
                    exc_info=True,
                )
                reduced_rows_list.append(group)
                continue

            agg_funcs = {}

            def aggregate_target(series):
                return (
                    (series.astype(float).mean() >= 0.5) if not series.empty else False
                )

            for col in group_for_cluster.columns:
                if col == "cluster":
                    continue
                col_type = group_for_cluster[col].dtype
                if col == commit_hash_col or col in info_columns:
                    agg_funcs[col] = "first"
                elif (
                    col in cluster_features
                ):  # Aggregate numeric features used for clustering
                    agg_funcs[col] = "mean"
                elif col in y_column:
                    agg_funcs[col] = aggregate_target
                elif pd.api.types.is_numeric_dtype(
                    col_type
                ):  # Aggregate other numeric cols
                    agg_funcs[col] = "mean"
                else:  # Keep first for any other non-numeric columns
                    agg_funcs[col] = "first"

            try:
                aggregated = (
                    group_for_cluster.groupby("cluster")
                    .agg(agg_funcs)
                    .reset_index(drop=True)
                )
                reduced_rows_list.append(aggregated)
            except Exception as agg_e:
                logger.error(
                    f"Rule Cluster: Aggregation failed for commit {commit[:7]}: {agg_e}. Keeping original rows.",
                    exc_info=True,
                )
                reduced_rows_list.append(group)

        if not reduced_rows_list:
            result_df = pd.DataFrame(columns=df.columns)
        else:
            result_df = pd.concat(reduced_rows_list, ignore_index=True, sort=False)

        dropped = initial_len - result_df.shape[0]
        if dropped > 0:
            logger.debug(f"Rule Cluster: Reduced rows by {dropped} via clustering.")
        return result_df
