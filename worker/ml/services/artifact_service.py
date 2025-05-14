# worker/ml/services/artifact_service.py
import logging
from pathlib import Path
from typing import Any, Optional

# import pickle # Remove pickle
import joblib  # Add joblib for safer serialization
import pandas as pd
import pyarrow as pa  # Import pyarrow for parquet writing
import pyarrow.parquet as pq
import s3fs

# Import the new interface
from services.interfaces import IArtifactService

from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


# Inherit from the interface
class ArtifactService(IArtifactService):
    """Handles saving and loading of ML artifacts to/from S3."""

    def __init__(self):
        self._fs = None  # Use a private attribute to store the instance
        logger.debug("ArtifactService instance created (S3 client lazy loaded).")

    @property
    def fs(self) -> s3fs.S3FileSystem:
        """Lazy Initializer for the S3FileSystem instance."""
        if self._fs is None:
            logger.info(
                "Initializing S3FileSystem client on demand for ArtifactService..."
            )
            try:
                self._fs = s3fs.S3FileSystem(**settings.s3_storage_options)
                logger.info(
                    "S3 FileSystem client initialized successfully for ArtifactService."
                )
            except Exception as e:
                logger.error(
                    f"Failed to initialize S3 FileSystem client on demand: {e}",
                    exc_info=True,
                )
                raise RuntimeError("Failed to initialize S3 client") from e
        return self._fs

    def _get_s3_path(self, artifact_uri: str) -> str:
        """Removes the 's3://' prefix."""
        if (
            not artifact_uri
            or not isinstance(artifact_uri, str)
            or not artifact_uri.startswith("s3://")
        ):
            raise ValueError(f"Invalid S3 URI format provided: '{artifact_uri}'")
        return artifact_uri.replace("s3://", "", 1)

    def save_artifact(self, artifact: Any, uri: str) -> bool:
        """Saves a Python object (e.g., model, scaler) to S3 using joblib."""
        if not uri:
            logger.error("Cannot save artifact: S3 URI is empty.")
            return False

        try:
            fs_client = self.fs
            s3_path = self._get_s3_path(uri)
            logger.info(f"Attempting to save artifact to: {uri} using joblib")

            parent_dir = Path(s3_path).parent
            if parent_dir != Path("."):
                fs_client.mkdirs(str(parent_dir), exist_ok=True)
                logger.debug(f"Ensured S3 directory exists: {parent_dir}")

            with fs_client.open(s3_path, "wb") as f:
                # Replace pickle.dump with joblib.dump
                joblib.dump(artifact, f, compress=3)  # Use compression

            logger.info(f"Successfully saved artifact to: {uri}")
            return True
        except Exception as e:
            logger.error(f"Error saving artifact to {uri}: {e}", exc_info=True)
            # Attempt cleanup only if fs client seems available
            fs_client = getattr(self, "_fs", None)
            if fs_client:
                try:
                    s3_path = self._get_s3_path(uri)
                    if fs_client.exists(s3_path):
                        fs_client.rm(s3_path)
                        logger.warning(
                            f"Removed potentially incomplete artifact at {uri} after save error."
                        )
                except Exception as cleanup_err:
                    logger.error(
                        f"Failed to clean up artifact at {uri} after save error: {cleanup_err}"
                    )
            return False

    def load_artifact(self, uri: str) -> Optional[Any]:
        """Loads a Python object from S3 using joblib."""
        if not uri:
            logger.error("Cannot load artifact: S3 URI is empty.")
            return None

        try:
            fs_client = self.fs
            s3_path = self._get_s3_path(uri)
            logger.info(f"Attempting to load artifact from: {uri} using joblib")

            if not fs_client.exists(s3_path):
                logger.error(f"Artifact not found at S3 location: {uri}")
                return None

            with fs_client.open(s3_path, "rb") as f:
                # Replace pickle.load with joblib.load
                artifact = joblib.load(f)

            logger.info(f"Successfully loaded artifact from: {uri}")
            return artifact
        except Exception as e:
            logger.error(f"Error loading artifact from {uri}: {e}", exc_info=True)
            return None

    def delete_artifact(self, uri: str) -> bool:
        """Deletes an artifact from S3."""
        if not uri:
            logger.error("Cannot delete artifact: S3 URI is empty.")
            return False

        try:
            fs_client = self.fs
            s3_path = self._get_s3_path(uri)
            logger.info(f"Attempting to delete artifact at: {uri}")

            if fs_client.exists(s3_path):
                fs_client.rm(s3_path)
                logger.info(f"Successfully deleted artifact: {uri}")
            else:
                logger.warning(f"Artifact not found at {uri}, no deletion performed.")
            return True
        except Exception as e:
            logger.error(f"Error deleting artifact {uri}: {e}", exc_info=True)
            return False

    def load_dataframe_artifact(self, uri: str) -> Optional[pd.DataFrame]:
        """Loads a DataFrame artifact from S3 (assuming Parquet format)."""
        if not uri:
            logger.error("Cannot load DataFrame artifact: S3 URI is empty.")
            return None

        try:
            fs_client = self.fs
            s3_path = self._get_s3_path(uri)
            logger.info(f"Attempting to load DataFrame artifact (Parquet) from: {uri}")

            if not fs_client.exists(s3_path):
                logger.error(f"DataFrame artifact not found at S3 location: {uri}")
                return None

            with fs_client.open(s3_path, "rb") as f:
                # Read using pyarrow engine for potentially better compatibility
                df = pd.read_parquet(f, engine="pyarrow")

            logger.info(f"Successfully loaded DataFrame artifact (Parquet) from: {uri}")
            return df
        except ImportError:
            logger.error("Pandas or PyArrow not installed.", exc_info=True)
            return None
        except Exception as e:
            logger.error(
                f"Error loading DataFrame artifact (Parquet) from {uri}: {e}",
                exc_info=True,
            )
            return None

    def write_dataframe_artifact(self, df: pd.DataFrame, uri: str) -> bool:
        """Writes a DataFrame artifact to S3 (assuming Parquet format)."""
        if df is None or not isinstance(df, pd.DataFrame):
            logger.error(
                "Cannot write DataFrame artifact: Input is not a valid DataFrame."
            )
            return False
        if not uri:
            logger.error("Cannot write DataFrame artifact: S3 URI is empty.")
            return False

        try:
            fs_client = self.fs
            s3_path = self._get_s3_path(uri)
            logger.info(f"Attempting to write DataFrame artifact (Parquet) to: {uri}")

            parent_dir = Path(s3_path).parent
            if parent_dir != Path("."):
                fs_client.mkdirs(str(parent_dir), exist_ok=True)

            # Convert DataFrame to Arrow Table before writing
            table = pa.Table.from_pandas(df, preserve_index=False)
            with fs_client.open(s3_path, "wb") as f:
                pq.write_table(table, f, compression="snappy")

            logger.info(f"Successfully wrote DataFrame artifact (Parquet) to: {uri}")
            return True
        except Exception as e:
            logger.error(
                f"Error writing DataFrame artifact (Parquet) to {uri}: {e}",
                exc_info=True,
            )
            # Attempt cleanup
            fs_client = getattr(self, "_fs", None)
            if fs_client:
                try:
                    s3_path = self._get_s3_path(uri)
                    if fs_client.exists(s3_path):
                        fs_client.rm(s3_path)
                except Exception:
                    pass  # Ignore cleanup errors
            return False
