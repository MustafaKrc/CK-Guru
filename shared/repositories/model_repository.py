# shared/repositories/model_repository.py
import logging
from typing import Any, Callable, Dict, Optional  # Added Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session  # Keep Session for type hint

from shared.core.config import settings
from shared.db.models import MLModel  # Keep model import

# Import Base Repository
from .base_repository import BaseRepository

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


# Inherit from BaseRepository AND the specific interface
class ModelRepository(BaseRepository[MLModel]):  # Specify ModelType

    # Add __init__ to accept session_factory
    def __init__(self, session_factory: Callable[[], Session]):
        super().__init__(session_factory)  # Initialize BaseRepository
        logger.debug("ModelRepository initialized.")

    def get_by_id(self, model_id: int) -> Optional[MLModel]:
        """Gets a single MLModel by ID."""
        with self._session_scope() as session:
            return session.get(MLModel, model_id)

    # Implement interface methods using session scope
    def find_latest_model_version(self, model_name: str) -> Optional[int]:
        """Gets the highest version number for a given model name."""
        logger.debug(f"ModelRepo: Finding latest version for model name: {model_name}")
        with self._session_scope() as session:
            stmt = select(func.max(MLModel.version)).where(MLModel.name == model_name)
            max_version = session.execute(stmt).scalar_one_or_none()
        return max_version

    def create_model_record(self, model_data: Dict[str, Any]) -> int:
        """Creates a new MLModel record and returns its ID."""
        logger.info(
            f"ModelRepo: Creating MLModel record for {model_data.get('name')} v{model_data.get('version')}"
        )
        with self._session_scope() as session:
            db_obj = MLModel(**model_data)
            session.add(db_obj)
            session.flush()  # Assign ID within the session scope
            model_id = db_obj.id
            # Commit happens implicitly when exiting _session_scope without errors
            # or explicitly if needed before returning ID?
            # Let's rely on the context manager's commit/rollback for now.
            # Need to ensure flush gets the ID before potential rollback.
            session.commit()  # Explicit commit might be safer before returning ID
            session.refresh(db_obj)  # Refresh after commit
        logger.info(f"ModelRepo: MLModel record created with ID: {model_id}")
        return model_id

    def set_model_artifact_path(self, model_id: int, s3_path: str):
        """Updates the s3_artifact_path for a given model ID."""
        logger.info(
            f"ModelRepo: Setting artifact path for MLModel {model_id} to {s3_path}"
        )
        with self._session_scope() as session:
            db_obj = session.get(MLModel, model_id)
            if db_obj:
                db_obj.s3_artifact_path = s3_path
                session.add(db_obj)
                session.commit()  # Commit the change
                logger.debug(
                    f"ModelRepo: MLModel {model_id} artifact path updated and committed."
                )
            else:
                logger.error(
                    f"ModelRepo: Cannot set artifact path - MLModel {model_id} not found."
                )
                raise ValueError(
                    f"MLModel {model_id} not found during artifact path update."
                )
