# worker/dataset/services/output_writer.py
import logging
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import s3fs

from shared.core.config import settings

# Import the interface
from .interfaces import IOutputWriter

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


class OutputWriter(IOutputWriter):  # Implement interface
    """Handles writing the final dataset to object storage."""

    def __init__(self, storage_options: Dict):
        self.storage_options = storage_options
        self._fs: Optional[s3fs.S3FileSystem] = (
            None  # Type hint for lazy loaded attribute
        )
        logger.debug("OutputWriter initialized.")

    @property
    def fs(self) -> s3fs.S3FileSystem:
        """Lazy Initializer for the S3FileSystem instance."""
        if self._fs is None:
            logger.info("Initializing S3FileSystem client for OutputWriter...")
            try:
                self._fs = s3fs.S3FileSystem(**self.storage_options)
                logger.info("S3 FileSystem client initialized successfully.")
            except Exception as e:
                logger.error(
                    f"Failed to initialize S3 FileSystem client on demand: {e}",
                    exc_info=True,
                )
                raise RuntimeError("Failed to initialize S3 client") from e
        return self._fs

    def _get_s3_path(self, s3_uri: str) -> str:
        """Removes 's3://' prefix if present."""
        if s3_uri.startswith("s3://"):
            return s3_uri.replace("s3://", "", 1)
        logger.warning(
            f"Output URI '{s3_uri}' does not start with 's3://'. Using as is."
        )
        return s3_uri

    def clear_existing(self, s3_uri: str):
        """Deletes the object at the given S3 URI if it exists."""
        try:
            s3_path = self._get_s3_path(s3_uri)
            if self.fs.exists(s3_path):  # Access fs property to trigger init if needed
                logger.warning(f"Attempting to remove existing object at: {s3_uri}")
                self.fs.rm(s3_path)
                logger.info(f"Removed existing object at {s3_uri}")
            else:
                logger.debug(f"No existing object found at {s3_uri} to clear.")
        except Exception as e:
            # Log error but don't fail the whole process just for cleanup failure
            logger.error(
                f"Could not ensure removal of existing object at {s3_uri}: {e}. Proceeding anyway.",
                exc_info=False,
            )

    def write_parquet(
        self, df: pd.DataFrame, s3_uri: str, target_column_name: Optional[str] = None
    ):
        """Writes the DataFrame to a Parquet file in S3."""
        s3_path = self._get_s3_path(s3_uri)
        logger.info(f"Writing final dataset ({len(df)} rows) to s3://{s3_path}")
        try:
            # Ensure parent directory exists (s3fs might require this)
            parent = str(Path(s3_path).parent)
            if parent != ".":  # Avoid trying to create '.' directory
                self.fs.mkdirs(parent, exist_ok=True)  # Access fs property

            # Convert Pandas DataFrame to Arrow Table
            table = pa.Table.from_pandas(df, preserve_index=False)

            # --- Add Custom Metadata ---
            existing_metadata = (
                table.schema.metadata or {}
            )  # Get existing metadata or empty dict
            custom_metadata = existing_metadata.copy()  # Don't modify original
            if target_column_name:
                # Add the target column name. Ensure it's bytes-encoded.
                custom_metadata[b"label_column_name"] = target_column_name.encode(
                    "utf-8"
                )

            # Update the table schema with the new metadata
            if custom_metadata != existing_metadata:  # Only update if metadata changed
                updated_schema = table.schema.with_metadata(custom_metadata)
                table = table.cast(
                    updated_schema
                )  # Cast table to the schema with new metadata
            # ------------------------

            # Write using pyarrow.parquet.write_table with fsspec file handle
            with self.fs.open(s3_path, "wb") as f:
                pq.write_table(
                    table,
                    f,
                    compression="snappy",
                )

            logger.info(f"Successfully wrote final dataset to s3://{s3_path}")
        except Exception as write_err:
            logger.error(
                f"Error writing final dataset to s3://{s3_path}: {write_err}",
                exc_info=True,
            )
            # Attempt cleanup of potentially partial file
            try:
                if self.fs.exists(s3_path):
                    logger.warning(
                        f"Attempting cleanup of failed write at s3://{s3_path}"
                    )
                    self.fs.rm(s3_path)
            except Exception as cleanup_err:
                logger.error(
                    f"Failed cleanup after write error to s3://{s3_path}: {cleanup_err}"
                )
            raise write_err  # Re-raise the original writing error
