# shared/repositories/xai_result_repository.py
import logging
from typing import Optional, Dict, Any, List, Callable # Added Callable
from datetime import datetime, timezone

from sqlalchemy.orm import Session # Keep Session for type hint
from sqlalchemy import select, update

# Import Base Repository
from .base_repository import BaseRepository
# Import models and schemas needed
import shared.schemas as schemas
from shared.db.models import XAIResult # Keep model import
from shared.schemas.enums import XAIStatusEnum, XAITypeEnum
from shared.schemas.xai_job import XAIResultCreate # Use the Create schema

logger = logging.getLogger(__name__)

# Inherit from BaseRepository AND the specific interface
class XaiResultRepository(BaseRepository[XAIResult]): # Specify ModelType

    # Add __init__ to accept session_factory
    def __init__(self, session_factory: Callable[[], Session]):
        super().__init__(session_factory) # Initialize BaseRepository
        logger.debug("XaiResultRepository initialized.")

    # --- Implement interface methods using session scope ---
    def find_existing_xai_result_id_sync(self, inference_job_id: int, xai_type: XAITypeEnum) -> Optional[int]:
        """Checks if an XAI result for a given job/type already exists."""
        with self._session_scope() as session:
            stmt = select(XAIResult.id).where(
                XAIResult.inference_job_id == inference_job_id,
                XAIResult.xai_type == xai_type
            ).limit(1)
            result_id = session.execute(stmt).scalar_one_or_none()
        return result_id

    def create_pending_xai_result_sync(self, inference_job_id: int, xai_type: XAITypeEnum) -> Optional[int]:
        """Creates a pending XAIResult record synchronously and returns its ID."""
        xai_result_id = None
        try:
            with self._session_scope() as session:
                logger.info(f"XaiRepo: Creating PENDING XAIResult record for Job {inference_job_id}, Type: {xai_type.value}")
                xai_create = schemas.XAIResultCreate(inference_job_id=inference_job_id, xai_type=xai_type)
                db_obj = XAIResult(**xai_create.model_dump())
                session.add(db_obj)
                session.flush() # Flush to get the ID
                session.commit() 
                session.refresh(db_obj) # Refresh to ensure we have the latest state
                xai_result_id = db_obj.id
                # Commit happens automatically on context exit if no error
            if xai_result_id:
                logger.info(f"XaiRepo: Created XAIResult ID: {xai_result_id}")
            else: # Should not happen if flush worked, but defensive check
                logger.error(f"XaiRepo: Failed to get ID after flush for Job {inference_job_id}, Type {xai_type.value}")
        except Exception as e:
            logger.error(f"XaiRepo: Failed to create pending XAIResult for Job {inference_job_id}, Type {xai_type.value}: {e}", exc_info=True)
            # Rollback is handled by context manager
        return xai_result_id

    def get_xai_result_sync(self, xai_result_id: int) -> Optional[XAIResult]:
         """Synchronously fetches an XAIResult record by ID."""
         logger.debug(f"XaiRepo: Fetching XAIResult {xai_result_id}")
         with self._session_scope() as session:
             # session.get is efficient for PK lookup
             result = session.get(XAIResult, xai_result_id)
         return result

    def update_xai_result_sync(
        self,
        xai_result_id: int,
        status: XAIStatusEnum,
        message: Optional[str] = None,
        result_data: Optional[Dict] = None,
        task_id: Optional[str] = None,
        is_start: bool = False,
        commit: bool = True # This flag is less relevant now with context manager
    ):
        """Updates an XAIResult record synchronously."""
        try:
            with self._session_scope() as session:
                xai_record = session.get(XAIResult, xai_result_id)
                if not xai_record:
                    logger.error(f"XaiRepo: Cannot update XAIResult: ID {xai_result_id} not found.")
                    raise ValueError(f"XAIResult record {xai_result_id} not found for update.")

                logger.info(f"XaiRepo: Updating XAIResult {xai_result_id} status to {status.value}")
                xai_record.status = status
                if message: xai_record.status_message = message[:1000]
                if result_data is not None: xai_record.result_data = result_data
                if task_id: xai_record.celery_task_id = task_id
                if is_start and xai_record.started_at is None:
                    xai_record.started_at = datetime.now(timezone.utc)
                if status in [XAIStatusEnum.SUCCESS, XAIStatusEnum.FAILED, XAIStatusEnum.REVOKED]:
                     xai_record.completed_at = datetime.now(timezone.utc)

                session.add(xai_record)
                session.commit() # ensure commit happens...
            logger.debug(f"XaiRepo: XAIResult {xai_result_id} update committed.")
        except Exception as e:
            logger.error(f"XaiRepo: Failed to update XAIResult DB entry for ID {xai_result_id}: {e}", exc_info=True)
            # Rollback handled by context manager
            raise # Re-raise

    def update_xai_task_id_sync(self, xai_result_id: int, task_id: str):
        """Synchronously updates only the celery_task_id for an XAIResult."""
        try:
            with self._session_scope() as session:
                xai_record = session.get(XAIResult, xai_result_id)
                if not xai_record:
                    logger.error(f"XaiRepo: Cannot update task ID for XAIResult: ID {xai_result_id} not found.")
                    raise ValueError(f"XAIResult record {xai_result_id} not found for task ID update.")
                xai_record.celery_task_id = task_id
                session.add(xai_record)
                # Commit happens automatically
            logger.debug(f"XaiRepo: Set task ID {task_id} for XAIResult {xai_result_id} and committed.")
        except Exception as e:
            logger.error(f"XaiRepo: Failed to update task ID for XAIResult {xai_result_id}: {e}", exc_info=True)
            raise # Re-raise

    def mark_xai_results_failed_sync(self, xai_result_ids: List[int], message: str):
        """Synchronously marks a list of XAIResult records as FAILED."""
        if not xai_result_ids: return
        try:
            with self._session_scope() as session:
                logger.warning(f"XaiRepo: Marking XAIResults {xai_result_ids} as FAILED. Reason: {message}")
                stmt = (
                    update(XAIResult)
                    .where(XAIResult.id.in_(xai_result_ids))
                    .values(
                        status=XAIStatusEnum.FAILED,
                        status_message=message[:1000],
                        completed_at=datetime.now(timezone.utc)
                     )
                    .execution_options(synchronize_session=False) # Important for bulk updates
                )
                session.execute(stmt)
                # Commit happens automatically
        except Exception as e:
            logger.error(f"XaiRepo: Failed to bulk mark XAIResults as FAILED: {e}", exc_info=True)
            raise # Re-raise