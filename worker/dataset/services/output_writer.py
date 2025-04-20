# worker/dataset/services/output_writer.py
import logging
from typing import Dict
from pathlib import Path

import pandas as pd
import s3fs # Import s3fs

from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

class OutputWriter:
    """Handles writing the final dataset to object storage."""

    def __init__(self, storage_options: Dict):
        self.storage_options = storage_options
        self._fs = None # Initialize lazily

    @property
    def fs(self) -> s3fs.S3FileSystem:
        """Lazy Initializer for the S3FileSystem instance."""
        if self._fs is None:
            logger.info("Initializing S3FileSystem client for OutputWriter...")
            try:
                self._fs = s3fs.S3FileSystem(**self.storage_options)
                logger.info("S3 FileSystem client initialized successfully for OutputWriter.")
            except Exception as e:
                logger.error(f"Failed to initialize S3 FileSystem client on demand: {e}", exc_info=True)
                raise RuntimeError("Failed to initialize S3 client") from e
        return self._fs

    def _get_s3_path(self, s3_uri: str) -> str:
        """Removes 's3://' prefix if present."""
        if s3_uri.startswith("s3://"):
            return s3_uri.replace("s3://", "", 1)
        logger.warning(f"Output URI '{s3_uri}' does not start with 's3://'. Using as is.")
        return s3_uri

    def clear_existing(self, s3_uri: str):
        """Deletes the object at the given S3 URI if it exists."""
        try:
            s3_path = self._get_s3_path(s3_uri)
            if self.fs.exists(s3_path): # Access fs property to trigger init if needed
                logger.warning(f"Attempting to remove existing object at: {s3_uri}")
                self.fs.rm(s3_path)
                logger.info(f"Removed existing object at {s3_uri}")
        except Exception as e:
            # Log error but don't fail the whole process just for cleanup failure
            logger.error(f"Could not ensure removal of existing object at {s3_uri}: {e}. Proceeding anyway.", exc_info=False)

    def write_parquet(self, df: pd.DataFrame, s3_uri: str):
        """Writes the DataFrame to a Parquet file in S3."""
        logger.info(f"Writing final dataset ({len(df)} rows) to {s3_uri}")
        try:
            # Ensure parent directory exists (s3fs might require this)
            s3_path = self._get_s3_path(s3_uri)
            parent = str(Path(s3_path).parent)
            if parent != '.': # Avoid trying to create '.' directory
                self.fs.mkdirs(parent, exist_ok=True) # Access fs property

            df.to_parquet(
                s3_uri, # Pass the full URI including s3://
                engine='pyarrow',
                compression='snappy',
                index=False,
                storage_options=self.storage_options # Pass storage options directly
            )
            logger.info(f"Successfully wrote final dataset to {s3_uri}")
        except Exception as write_err:
            logger.error(f"Error writing final dataset to {s3_uri}: {write_err}", exc_info=True)
            # Attempt cleanup of potentially partial file
            try:
                 if self.fs.exists(s3_path):
                     logger.warning(f"Attempting cleanup of failed write at {s3_uri}")
                     self.fs.rm(s3_path)
            except Exception as cleanup_err:
                 logger.error(f"Failed cleanup after write error to {s3_uri}: {cleanup_err}")
            raise write_err # Re-raise the original writing error