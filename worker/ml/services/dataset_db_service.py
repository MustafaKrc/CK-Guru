# worker/ml/services/dataset_db_service.py
import logging
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from shared.db.models import Dataset, DatasetStatusEnum
from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

def get_dataset_status_and_path(session: Session, dataset_id: int) -> Tuple[Optional[DatasetStatusEnum], Optional[str]]:
    """Fetches dataset status and storage path."""
    logger.debug(f"Fetching status/path for Dataset {dataset_id}.")
    dataset = session.get(Dataset, dataset_id)
    if not dataset:
        logger.warning(f"Dataset {dataset_id} not found in DB.")
        return None, None
    return dataset.status, dataset.storage_path