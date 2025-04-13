# worker/ml/services/model_db_service.py
import logging
from typing import Optional, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from shared.db.models import MLModel
from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

def find_latest_model_version(session: Session, model_name: str) -> Optional[int]:
    """Gets the highest version number for a given model name."""
    logger.debug(f"Finding latest version for model name: {model_name}")
    stmt = select(func.max(MLModel.version)).where(MLModel.name == model_name)
    max_version = session.execute(stmt).scalar_one_or_none()
    return max_version

def create_model_record(session: Session, model_data: Dict[str, Any]) -> int:
    """Creates a new MLModel record and returns its ID."""
    logger.info(f"Creating MLModel record for {model_data.get('name')} v{model_data.get('version')}")
    # Ensure required fields are present if necessary, or rely on DB constraints/defaults
    db_obj = MLModel(**model_data)
    session.add(db_obj)
    session.flush() # Assign ID
    model_id = db_obj.id
    logger.info(f"MLModel record created with ID: {model_id}")
    return model_id

def set_model_artifact_path(session: Session, model_id: int, s3_path: str):
    """Updates the s3_artifact_path for a given model ID."""
    logger.info(f"Setting artifact path for MLModel {model_id} to {s3_path}")
    db_obj = session.get(MLModel, model_id)
    if db_obj:
        db_obj.s3_artifact_path = s3_path
        session.add(db_obj) # Add to session to track changes
        logger.debug(f"MLModel {model_id} artifact path updated in session.")
    else:
        logger.error(f"Cannot set artifact path: MLModel {model_id} not found.")
        # Raise an error? Or just log? Let's log for now.
        # raise ValueError(f"MLModel {model_id} not found during artifact path update.")