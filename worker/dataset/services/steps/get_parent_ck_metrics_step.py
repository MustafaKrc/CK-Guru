# worker/dataset/services/steps/get_parent_ck_metrics_step.py
import logging
from typing import Set, Tuple

import pandas as pd
import sqlalchemy as sa
from sqlalchemy import select

from services.interfaces import IDatasetGeneratorStep
from services.context import DatasetContext
from shared.repositories import CKMetricRepository # Import concrete repository
from shared.db.models import CKMetric # Import model for query
from shared.db import CK_METRIC_COLUMNS # Import column list
from shared.utils.pipeline_logging import StepLogger

logger = logging.getLogger(__name__)

class GetParentCKMetricsStep(IDatasetGeneratorStep):
    """Fetches parent CK metrics for a batch DataFrame."""
    name = "Get Parent CK Metrics"

    def execute(self, context: DatasetContext, *, ck_repo: CKMetricRepository, **kwargs) -> DatasetContext:
        log_prefix = f"Task {context.task_instance.request.id} - Step [{self.name}]"
        step_logger = StepLogger(logger, log_prefix=log_prefix)

        if context.processed_dataframe is None or context.processed_dataframe.empty:
            step_logger.warning("Input DataFrame is None or empty, skipping parent fetch.")
            # Add empty parent columns if df exists but is empty? Or handle downstream?
            # Let's handle downstream for now.
            return context

        df = context.processed_dataframe
        step_logger.info(f"Fetching parent CK metrics for DataFrame with shape {df.shape}...")

        required_cols = ['repository_id', 'parent_hashes', 'file', 'class'] # Expect 'class' after DataLoader rename
        if not all(col in df.columns for col in required_cols):
            missing = [c for c in required_cols if c not in df.columns]
            step_logger.error(f"Missing required columns for parent lookup: {missing}. Skipping step.")
            context.warnings.append(f"{self.name}: Missing required columns: {missing}")
            # Add empty parent columns for consistency downstream?
            df['_parent_metric_found'] = False
            for col in CK_METRIC_COLUMNS: df[f"parent_{col}"] = pd.NA
            context.processed_dataframe = df
            return context

        parent_data_map = {}
        lookup_keys: Set[Tuple] = set()
        batch_map = {} # Map original df index to list of lookup keys

        for idx, row in df.iterrows():
            parent_hashes_str = row.get('parent_hashes')
            # Get the *first* parent hash
            parent_hash = parent_hashes_str.split()[0] if parent_hashes_str else None
            if parent_hash:
                # Key: (repo_id, parent_hash, file_path, class_name)
                key = (row['repository_id'], parent_hash, row['file'], row.get('class'))
                lookup_keys.add(key)
                if idx not in batch_map: batch_map[idx] = []
                batch_map[idx].append(key) # Store keys associated with this row index

        if lookup_keys:
            step_logger.debug(f"Looking up {len(lookup_keys)} unique parent metric keys...")
            # Use the repository's session scope internally
            try:
                with ck_repo._session_scope() as session:
                    filters = []
                    for repo_id, phash, pfile, pclass in lookup_keys:
                        # Map 'class' back to model's 'class_name' for query if necessary
                        filters.append(
                            sa.and_(
                                CKMetric.repository_id == repo_id,
                                CKMetric.commit_hash == phash,
                                CKMetric.file == pfile,
                                CKMetric.class_name == pclass # Use model attribute name
                            )
                        )
                    if filters:
                        parent_stmt = select(CKMetric).where(sa.or_(*filters))
                        parent_results = session.execute(parent_stmt).scalars().all()
                        for pm in parent_results:
                            # Use model attribute name 'class_name' for map key
                            key = (pm.repository_id, pm.commit_hash, pm.file, pm.class_name)
                            parent_data_map[key] = {col: getattr(pm, col, None) for col in CK_METRIC_COLUMNS}
                        step_logger.info(f"Found parent metrics for {len(parent_data_map)} keys.")
            except Exception as e:
                 step_logger.error(f"Database error fetching parent metrics: {e}", exc_info=True)
                 context.warnings.append(f"{self.name}: DB error fetching parents: {e}")
                 # Continue, but parent metrics will be missing

        # --- Join results back to the DataFrame ---
        final_data_list = []
        parent_cols_template = {f"parent_{col}": pd.NA for col in CK_METRIC_COLUMNS}

        for idx in df.index: # Iterate using original index
            found = False
            parent_metric_data = None
            keys_for_row = batch_map.get(idx, []) # Get keys for this row
            if keys_for_row:
                 for key in keys_for_row:
                      if key in parent_data_map:
                           parent_metric_data = parent_data_map[key]
                           found = True
                           break # Found the first parent's metrics
            row_dict = {'_parent_metric_found': found}
            row_dict.update(parent_cols_template) # Start with NAs
            if parent_metric_data:
                 # Map parent data using standard CK_METRIC_COLUMNS keys
                 row_dict.update({f"parent_{col}": parent_metric_data.get(col) for col in CK_METRIC_COLUMNS})
            final_data_list.append(row_dict)

        # Create DataFrame with the same index as the original batch df
        parent_df = pd.DataFrame(final_data_list, index=df.index)
        if '_parent_metric_found' in parent_df.columns:
             parent_df['_parent_metric_found'] = parent_df['_parent_metric_found'].astype(bool)

        # Join the parent metrics DataFrame back to the original df
        context.processed_dataframe = df.join(parent_df)
        step_logger.info("Parent CK metrics joined to DataFrame.")

        return context