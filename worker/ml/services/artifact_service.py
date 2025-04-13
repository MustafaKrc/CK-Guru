# worker/ml/services/artifact_service.py
import logging
import pickle
from pathlib import Path
from typing import Any, Optional

import s3fs
from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

class ArtifactService:
    """Handles saving and loading of ML artifacts to/from S3."""

    def __init__(self):
        # --- REMOVE initialization from here ---
        # self.fs = None # Initialize as None
        # try:
        #     self.fs = s3fs.S3FileSystem(**settings.s3_storage_options)
        #     logger.info("S3 FileSystem client initialized for ArtifactService.")
        # except Exception as e:
        #     logger.error(f"Failed to initialize S3 FileSystem client: {e}", exc_info=True)
        self._fs = None # Use a private attribute to store the instance


    # Initialize the S3FileSystem client lazily when first accessed.
    # This is because s3fs is not fork safe and should not be initialized
    # in the main process. Instead, we initialize it when the worker
    # process is forked and the worker is ready to handle tasks.

    @property
    def fs(self) -> s3fs.S3FileSystem:
        """Lazy Initializer for the S3FileSystem instance."""
        # --- Initialize lazily on first access ---
        if self._fs is None:
            logger.info("Initializing S3FileSystem client on demand...")
            try:
                self._fs = s3fs.S3FileSystem(**settings.s3_storage_options)
                logger.info("S3 FileSystem client initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize S3 FileSystem client on demand: {e}", exc_info=True)
                # Raise an error or handle appropriately - raising might be better here
                # as subsequent calls will fail anyway.
                raise RuntimeError("Failed to initialize S3 client") from e
        return self._fs

    def _get_s3_path(self, artifact_uri: str) -> str:
        """Removes the 's3://' prefix."""
        if not artifact_uri.startswith("s3://"):
            raise ValueError(f"Invalid S3 URI format: {artifact_uri}")
        return artifact_uri.replace("s3://", "", 1)

    def save_artifact(self, artifact: Any, s3_uri: str) -> bool:
        """Saves a Python object (e.g., model, scaler) to S3 using pickle."""
        if not s3_uri:
            logger.error("Cannot save artifact: S3 URI is empty.")
            return False

        try:
            # Access self.fs - this will trigger initialization if needed
            fs_client = self.fs
            s3_path = self._get_s3_path(s3_uri)
            logger.info(f"Attempting to save artifact to: {s3_uri}")

            parent_dir = Path(s3_path).parent
            if parent_dir != Path("."):
                fs_client.mkdirs(str(parent_dir), exist_ok=True)
                logger.debug(f"Ensured S3 directory exists: {parent_dir}")

            with fs_client.open(s3_path, 'wb') as f:
                pickle.dump(artifact, f)

            logger.info(f"Successfully saved artifact to: {s3_uri}")
            return True
        except Exception as e:
            # Log error including potential initialization failures from self.fs access
            logger.error(f"Error saving artifact to {s3_uri}: {e}", exc_info=True)
            # Attempt cleanup only if fs client seems available
            fs_client = getattr(self, '_fs', None) # Check if it was ever initialized
            if fs_client:
                try:
                     s3_path = self._get_s3_path(s3_uri) # Recalculate path just in case
                     if fs_client.exists(s3_path):
                         fs_client.rm(s3_path)
                         logger.warning(f"Removed potentially incomplete artifact at {s3_uri} after save error.")
                except Exception as cleanup_err:
                     logger.error(f"Failed to clean up artifact at {s3_uri} after save error: {cleanup_err}")
            return False


    def load_artifact(self, s3_uri: str) -> Optional[Any]:
        """Loads a Python object from S3 using pickle."""
        if not s3_uri:
            logger.error("Cannot load artifact: S3 URI is empty.")
            return None

        try:
            fs_client = self.fs # Trigger lazy init if needed
            s3_path = self._get_s3_path(s3_uri)
            logger.info(f"Attempting to load artifact from: {s3_uri}")

            if not fs_client.exists(s3_path):
                logger.error(f"Artifact not found at S3 location: {s3_uri}")
                return None

            with fs_client.open(s3_path, 'rb') as f:
                artifact = pickle.load(f)

            logger.info(f"Successfully loaded artifact from: {s3_uri}")
            return artifact
        except Exception as e:
            logger.error(f"Error loading artifact from {s3_uri}: {e}", exc_info=True)
            return None


    def delete_artifact(self, s3_uri: str) -> bool:
        """Deletes an artifact from S3."""
        if not s3_uri:
            logger.error("Cannot delete artifact: S3 URI is empty.")
            return False

        try:
            fs_client = self.fs # Trigger lazy init if needed
            s3_path = self._get_s3_path(s3_uri)
            logger.info(f"Attempting to delete artifact at: {s3_uri}")

            if fs_client.exists(s3_path):
                fs_client.rm(s3_path)
                logger.info(f"Successfully deleted artifact: {s3_uri}")
            else:
                logger.warning(f"Artifact not found at {s3_uri}, no deletion performed.")
            return True
        except Exception as e:
            logger.error(f"Error deleting artifact {s3_uri}: {e}", exc_info=True)
            return False

# Create a singleton instance (initialization is now lazy)
artifact_service = ArtifactService()