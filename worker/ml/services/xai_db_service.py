# worker/ml/services/xai_db_service.py
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import select, update

# Import models and schemas needed
import shared.schemas as schemas
from shared.db.models import XAIResult
from shared.schemas.enums import XAIStatusEnum, XAITypeEnum
from shared.schemas.xai_job import XAIResultCreate # Use the Create schema
from shared.db_session import get_sync_db_session # Import sync session helper

logger = logging.getLogger(__name__)

# --- Synchronous CRUD operations for XAIResult needed by Celery tasks ---

def find_existing_xai_result_id_sync(session: Session, inference_job_id: int, xai_type: XAITypeEnum) -> Optional[int]:
    """Checks if an XAI result for a given job/type already exists."""
    stmt = select(XAIResult.id).where(
        XAIResult.inference_job_id == inference_job_id,
        XAIResult.xai_type == xai_type
    ).limit(1)
    result_id = session.execute(stmt).scalar_one_or_none()
    return result_id

def create_pending_xai_result_sync(session: Session, inference_job_id: int, xai_type: XAITypeEnum) -> Optional[int]:
    """Creates a pending XAIResult record synchronously and returns its ID."""
    try:
        logger.info(f"DB Service: Creating PENDING XAIResult record for Job {inference_job_id}, Type: {xai_type.value}")
        # Use the Create schema which sets default status
        xai_create = schemas.XAIResultCreate(inference_job_id=inference_job_id, xai_type=xai_type)
        db_obj = XAIResult(**xai_create.model_dump())
        session.add(db_obj)
        session.flush() # Flush to get the ID
        xai_result_id = db_obj.id
        logger.info(f"DB Service: Created XAIResult ID: {xai_result_id}")
        # Commit happens outside this specific function (e.g., after dispatch loop)
        return xai_result_id
    except Exception as e:
        logger.error(f"DB Service: Failed to create pending XAIResult for Job {inference_job_id}, Type {xai_type.value}: {e}", exc_info=True)
        session.rollback() # Rollback the specific creation attempt
        return None

def get_xai_result_sync(session: Session, xai_result_id: int) -> Optional[XAIResult]:
     """Synchronously fetches an XAIResult record by ID."""
     logger.debug(f"DB Service: Fetching XAIResult {xai_result_id}")
     return session.get(XAIResult, xai_result_id)


def update_xai_result_sync(
    session: Session,
    xai_result_id: int,
    status: XAIStatusEnum,
    message: Optional[str] = None,
    result_data: Optional[Dict] = None,
    task_id: Optional[str] = None,
    is_start: bool = False,
    commit: bool = True # Allow controlling commit from caller
):
    """Updates an XAIResult record synchronously."""
    try:
        xai_record = session.get(XAIResult, xai_result_id)
        if not xai_record:
            logger.error(f"Cannot update XAIResult: ID {xai_result_id} not found.")
            return

        logger.info(f"Updating XAIResult {xai_result_id} status to {status.value}")
        xai_record.status = status
        if message: xai_record.status_message = message[:1000] # Truncate
        if result_data: xai_record.result_data = result_data
        if task_id: xai_record.celery_task_id = task_id
        if is_start and xai_record.started_at is None:
            xai_record.started_at = datetime.now(timezone.utc)
        if status in [XAIStatusEnum.SUCCESS, XAIStatusEnum.FAILED, XAIStatusEnum.REVOKED]:
             xai_record.completed_at = datetime.now(timezone.utc)

        session.add(xai_record)
        if commit:
             session.commit()
             logger.debug(f"XAIResult {xai_result_id} update committed.")
    except Exception as e:
        logger.error(f"Failed to update XAIResult DB entry for ID {xai_result_id}: {e}", exc_info=True)
        session.rollback()
        # Optionally re-raise if the caller needs to know about the DB error
        # raise

def update_xai_task_id_sync(session: Session, xai_result_id: int, task_id: str):
    """Synchronously updates only the celery_task_id for an XAIResult."""
    try:
        xai_record = session.get(XAIResult, xai_result_id)
        if not xai_record:
            logger.error(f"DB Service: Cannot update task ID for XAIResult: ID {xai_result_id} not found.")
            return
        xai_record.celery_task_id = task_id
        session.add(xai_record)
        # Commit is handled by the caller (orchestration task)
        logger.debug(f"DB Service: Set task ID {task_id} for XAIResult {xai_result_id} in session.")
    except Exception as e:
        logger.error(f"DB Service: Failed to update task ID for XAIResult {xai_result_id}: {e}", exc_info=True)
        session.rollback()


def mark_xai_results_failed_sync(session: Session, xai_result_ids: List[int], message: str):
    """Synchronously marks a list of XAIResult records as FAILED."""
    if not xai_result_ids: return
    try:
        logger.warning(f"DB Service: Marking XAIResults {xai_result_ids} as FAILED. Reason: {message}")
        stmt = (
            update(XAIResult)
            .where(XAIResult.id.in_(xai_result_ids))
            .values(
                status=XAIStatusEnum.FAILED,
                status_message=message[:1000],
                completed_at=datetime.now(timezone.utc)
             )
            .execution_options(synchronize_session=False)
        )
        session.execute(stmt)
        # Commit is handled by the caller (orchestration task)
    except Exception as e:
        logger.error(f"DB Service: Failed to bulk mark XAIResults as FAILED: {e}", exc_info=True)
        session.rollback()