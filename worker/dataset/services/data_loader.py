# worker/dataset/services/data_loader.py
import logging
from typing import List, Generator

import pandas as pd
import sqlalchemy as sa
from sqlalchemy import select, func
from sqlalchemy.orm import Session, aliased

from shared.db.models import BotPattern, CommitGuruMetric, CKMetric
from shared.core.config import settings
from .processing_steps import ProcessingSteps, COMMIT_GURU_METRIC_COLUMNS, CK_METRIC_COLUMNS # Import columns

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

class DataLoader:
    """Handles fetching and streaming data batches from the database."""
    def __init__(self, session: Session, repository_id: int, bot_patterns: List[BotPattern]):
        self.session = session
        self.repository_id = repository_id
        self.bot_patterns = bot_patterns
        self.cgm_alias = aliased(CommitGuruMetric, name="cgm")
        self.ckm_alias = aliased(CKMetric, name="ckm")
        self.base_query = self._build_base_query()

    def _build_base_query(self):
        """Constructs the base SQLAlchemy query."""
        logger.debug("Building base data loading query...")
        query = (
            select(self.cgm_alias, self.ckm_alias)
            .join(self.ckm_alias, sa.and_(
                self.cgm_alias.repository_id == self.ckm_alias.repository_id,
                self.cgm_alias.commit_hash == self.ckm_alias.commit_hash
            ))
            .where(self.cgm_alias.repository_id == self.repository_id)
        )

        # Apply bot filters if patterns exist
        if self.bot_patterns:
            bot_condition = ProcessingSteps.get_bot_filter_condition(self.bot_patterns, self.cgm_alias)
            query = query.where(sa.not_(bot_condition))
            logger.debug("Applied bot filters to base query.")
        else:
            logger.debug("No bot patterns provided, skipping bot filtering.")

        return query

    def estimate_total_rows(self) -> int:
        """Estimates the total number of rows the query will return."""
        logger.debug("Estimating total rows for query...")
        try:
            count_query = select(func.count()).select_from(self.base_query.subquery())
            estimated_count = self.session.execute(count_query).scalar() or 1
            logger.debug(f"Estimated total rows: {estimated_count}")
            return estimated_count
        except Exception as e:
            logger.error(f"Failed to estimate total rows: {e}", exc_info=True)
            return 1 # Return 1 to avoid division by zero in progress calculation

    def stream_batches(self, batch_size: int) -> Generator[pd.DataFrame, None, None]:
        """Executes the query and yields data in Pandas DataFrame batches."""
        logger.info(f"Streaming data batches with size {batch_size}...")
        try:
            stream = self.session.execute(self.base_query).yield_per(batch_size)
            batch_num = 0
            for result_batch in stream.partitions(batch_size):
                batch_num += 1
                if not result_batch:
                    logger.debug(f"Batch {batch_num}: No data returned.")
                    continue

                start_time = pd.Timestamp.now()
                # Process rows into a list of dictionaries
                batch_data = []
                for row in result_batch:
                    # Access attributes directly from the aliased objects in the row tuple
                    cgm_data = {col: getattr(row.cgm, col, None) for col in COMMIT_GURU_METRIC_COLUMNS}
                    ckm_data = {col: getattr(row.ckm, col, None) for col in CK_METRIC_COLUMNS}
                    # Combine, ensuring no accidental overwrites if keys were common (unlikely here)
                    combined_data = {**cgm_data, **ckm_data}
                    combined_data['repository_id'] = self.repository_id # Add repo_id if needed downstream
                    batch_data.append(combined_data)

                if batch_data:
                    df = pd.DataFrame(batch_data)
                    end_time = pd.Timestamp.now()
                    logger.debug(f"Batch {batch_num}: Yielding DataFrame with shape {df.shape}. Time: {end_time - start_time}")
                    yield df
                else:
                     logger.debug(f"Batch {batch_num}: Contained rows but resulted in empty data list.")

            logger.info("Finished streaming all data batches.")
        except Exception as e:
            logger.error(f"Error during data batch streaming: {e}", exc_info=True)
            raise # Re-raise the error to stop the process