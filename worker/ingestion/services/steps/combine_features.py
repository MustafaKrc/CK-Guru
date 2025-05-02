# worker/ingestion/services/steps/combine_features.py
import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

from .base import IngestionStep, IngestionContext
from shared.core.config import settings
from shared.db import CK_METRIC_COLUMNS, COMMIT_GURU_METRIC_COLUMNS

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

class CombineFeaturesStep(IngestionStep):
    name = "Combine Features for Inference"

    def execute(self, context: IngestionContext) -> IngestionContext:
        if not context.is_single_commit_mode:
            self._log_info(context, "Skipping feature combination (not single commit mode).")
            return context

        self._log_info(context, "Combining extracted metrics into final feature set...")

        if not context.target_commit_hash:
            raise ValueError("Target commit hash missing for feature combination.")

        # --- Extract Target CommitGuru Data ---
        target_cgm_data_list = [d for d in context.raw_commit_guru_data if d.get('commit_hash') == context.target_commit_hash]
        if not target_cgm_data_list:
            raise ValueError(f"CommitGuru metrics missing for target commit {context.target_commit_hash[:7]}.")
        # Should only be one entry for the target commit
        target_cgm_data = target_cgm_data_list[0]
        # Select only the relevant guru metric columns
        guru_features = {col: target_cgm_data.get(col) for col in COMMIT_GURU_METRIC_COLUMNS}

        # --- Extract Target CK Data ---
        target_ck_df = context.raw_ck_metrics.get(context.target_commit_hash)
        if target_ck_df is None or target_ck_df.empty:
                # Allow proceeding without CK if needed? Depends on model. Assume error for now.
                raise ValueError(f"CK metrics missing for target commit {context.target_commit_hash[:7]}.")

        # --- Extract Parent CK Data (if available) ---
        parent_ck_df = pd.DataFrame() # Default empty
        if context.parent_commit_hash:
            parent_ck_df = context.raw_ck_metrics.get(context.parent_commit_hash, pd.DataFrame())
            if parent_ck_df.empty:
                    self._log_warning(context, f"Parent CK metrics for {context.parent_commit_hash[:7]} were empty or not calculated. Delta features will be NaN.")
        else:
                self._log_warning(context, "No parent commit hash available, delta features will be NaN.")


        # --- Merge Target and Parent CK ---
        # Add merge keys (use actual DB attribute names)
        target_ck_df['merge_key_file'] = target_ck_df['file']
        target_ck_df['merge_key_class'] = target_ck_df['class_name']
        if not parent_ck_df.empty:
            parent_ck_df['merge_key_file'] = parent_ck_df['file']
            parent_ck_df['merge_key_class'] = parent_ck_df['class_name']
            # Rename parent CK columns *before* merge
            parent_ck_df_renamed = parent_ck_df.rename(
                columns={col: f"parent_{col}" for col in CK_METRIC_COLUMNS}
            )
            # Use outer merge to keep all target rows
            merged_df = pd.merge(
                target_ck_df,
                parent_ck_df_renamed,
                on=['merge_key_file', 'merge_key_class'], # Merge on shared keys
                how='left',
                suffixes=('', '_parent') # Suffix for non-metric parent columns if any overlap
            )
        else:
            # If no parent data, just use target data and add placeholder parent columns
            merged_df = target_ck_df.copy()
            for col in CK_METRIC_COLUMNS:
                    merged_df[f"parent_{col}"] = np.nan

        # --- Calculate Delta Metrics ---
        self._log_info(context, "Calculating delta metrics...")
        for col in CK_METRIC_COLUMNS:
            target_col = col
            parent_col = f"parent_{col}"
            delta_col = f"d_{col}"

            if target_col in merged_df.columns and parent_col in merged_df.columns:
                target_numeric = pd.to_numeric(merged_df[target_col], errors='coerce')
                parent_numeric = pd.to_numeric(merged_df[parent_col], errors='coerce')
                merged_df[delta_col] = target_numeric - parent_numeric
                mask_invalid = target_numeric.isna() | parent_numeric.isna()
                merged_df.loc[mask_invalid, delta_col] = np.nan
            else:
                    merged_df[delta_col] = np.nan # Set delta to NaN if parent/target col missing

        # --- Combine with Guru Features and Finalize ---
        final_features_list = []
        for _, row in merged_df.iterrows():
            # Combine commit-level Guru features with row-level CK/Delta features
            combined_row = {**guru_features, **row.to_dict()}
            final_features_list.append(combined_row)

        if not final_features_list:
            raise RuntimeError("Feature combination resulted in empty list.")

        final_df = pd.DataFrame(final_features_list)

        # Drop temporary/intermediate columns
        cols_to_drop = [c for c in final_df.columns if c.startswith('parent_') or c.startswith('merge_key_')]
        final_df = final_df.drop(columns=cols_to_drop, errors='ignore')

        # Convert DataFrame to list of dictionaries for Celery transport
        # Ensure NaN/Inf are handled (e.g., converted to None)
        final_features_dict_list = final_df.replace([np.inf, -np.inf], np.nan).to_dict(orient='records')

        # Store the result (list of dicts) in the context
        context.final_combined_features = final_features_dict_list

        self._log_info(context, f"Finished combining features. Generated {len(final_features_dict_list)} feature sets (one per file/class).")
        return context