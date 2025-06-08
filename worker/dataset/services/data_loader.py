# worker/dataset/services/data_loader.py
import logging
from typing import Generator, List

import pandas as pd
import sqlalchemy as sa
from sqlalchemy import func, select

from shared.core.config import settings
from shared.db.models import (  # Import models directly for query construction
    BotPattern,
    CKMetric,
    CommitGuruMetric,
)
from shared.repositories import (  # Import Repositories if needed, but query uses models
    BotPatternRepository,
)

# Import BaseRepository for context manager access
from shared.repositories.base_repository import BaseRepository

# Import interfaces and specific repositories
from .interfaces import IDataLoader

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

# Constants (Consider moving these to a shared location if used elsewhere)
COMMIT_GURU_METRIC_COLUMNS = [  # Example, use the actual list
    "commit_hash",
    "parent_hashes",
    "author_name",
    "author_email",
    "author_date",
    "author_date_unix_timestamp",
    "commit_message",
    "is_buggy",
    "fix",
    "files_changed",
    "ns",
    "nd",
    "nf",
    "entropy",
    "la",
    "ld",
    "lt",
    "ndev",
    "age",
    "nuc",
    "exp",
    "rexp",
    "sexp",
]
CK_METRIC_COLUMNS = [  # Example, use the actual list
    "file",
    "class_name",
    "type",
    "cbo",
    "cboModified",
    "fanin",
    "fanout",
    "wmc",
    "dit",
    "noc",
    "rfc",
    "lcom",
    "lcom_norm",
    "tcc",
    "lcc",
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
    "uniqueWordsQty",
    "modifiers",
    "logStatementsQty",
]


class DataLoader(IDataLoader):  # Implement interface
    """Handles fetching and streaming data batches from the database using repositories."""

    def __init__(
        self,
        session_factory: callable,
        repository_id: int,
        bot_patterns: List[BotPattern],
    ):
        self.session_factory = session_factory  # Needed for base repo context manager
        self.repository_id = repository_id
        self.bot_patterns = bot_patterns
        # Repositories are not directly injected here; queries are built using models
        # We use the session_factory context manager for execution

        self.cgm_alias = sa.orm.aliased(CommitGuruMetric, name="cgm")
        self.ckm_alias = sa.orm.aliased(CKMetric, name="ckm")
        self.base_query = self._build_base_query()
        logger.debug(f"DataLoader initialized for repository ID: {self.repository_id}")

    def _build_base_query(self):
        """Constructs the base SQLAlchemy query."""
        logger.debug("Building base data loading query...")
        query = (
            select(self.cgm_alias, self.ckm_alias)
            .join(
                self.ckm_alias,
                sa.and_(
                    self.cgm_alias.repository_id == self.ckm_alias.repository_id,
                    self.cgm_alias.commit_hash == self.ckm_alias.commit_hash,
                ),
            )
            .where(self.cgm_alias.repository_id == self.repository_id)
        )

        return query

    def estimate_total_rows(self) -> int:
        """Estimates the total number of rows the query will return."""
        logger.debug("Estimating total rows for query...")
        # Use the BaseRepository context manager for the session
        with BaseRepository._session_scope(
            self
        ) as session:  # Access context manager via Base
            try:
                # Execute the count query within the session scope
                count_query = select(func.count()).select_from(
                    self.base_query.subquery()
                )
                estimated_count = session.execute(count_query).scalar() or 1
                logger.debug(f"Estimated total rows: {estimated_count}")
                return estimated_count
            except Exception as e:
                logger.error(f"Failed to estimate total rows: {e}", exc_info=True)
                return 1  # Return 1 to avoid division by zero

    def stream_batches(self, batch_size: int) -> Generator[pd.DataFrame, None, None]:
        """Executes the query and yields data in Pandas DataFrame batches."""
        logger.info(f"Streaming data batches with size {batch_size}...")
        # Use the BaseRepository context manager for the session
        with BaseRepository._session_scope(
            self
        ) as session:  # Access context manager via Base
            try:
                # Execute the main query within the session scope
                stream = session.execute(self.base_query).yield_per(batch_size)
                batch_num = 0
                for result_batch in stream.partitions(batch_size):
                    batch_num += 1
                    if not result_batch:
                        logger.debug(f"Batch {batch_num}: No data returned.")
                        continue

                    start_time = pd.Timestamp.now()
                    batch_data = []
                    for row in result_batch:
                        # Access attributes directly from the aliased ORM objects
                        cgm_data = {
                            col: getattr(row.cgm, col, None)
                            for col in COMMIT_GURU_METRIC_COLUMNS
                        }
                        ckm_data = {
                            col: getattr(row.ckm, col, None)
                            for col in CK_METRIC_COLUMNS
                        }

                        # Rename CKMetric model attributes to match DataFrame expectations if needed
                        # (Assuming model uses class_name, type_)
                        ckm_data["class"] = getattr(
                            row.ckm, "class_name", None
                        )  # Use model attribute name
                        ckm_data["type"] = getattr(
                            row.ckm, "type_", None
                        )  # Use model attribute name
                        # Remove the original keys based on model attribute names
                        ckm_data.pop("class_name", None)
                        ckm_data.pop("type_", None)

                        combined_data = {**cgm_data, **ckm_data}
                        combined_data["repository_id"] = (
                            self.repository_id
                        )  # Add repo_id
                        batch_data.append(combined_data)

                    if batch_data:
                        df = pd.DataFrame(batch_data)
                        end_time = pd.Timestamp.now()
                        logger.debug(
                            f"Batch {batch_num}: Yielding DataFrame with shape {df.shape}. Time: {end_time - start_time}"
                        )
                        yield df
                    else:
                        logger.debug(
                            f"Batch {batch_num}: Contained rows but resulted in empty data list."
                        )

                logger.info("Finished streaming all data batches.")
            except Exception as e:
                logger.error(f"Error during data batch streaming: {e}", exc_info=True)
                raise  # Re-raise the error to stop the process
