# backend/services/xai_service.py
import logging
from typing import List, Optional

from app import crud
from app.core.celery_app import backend_celery_app

# Import TaskStatusService if it exists, otherwise use AsyncResult directly for now
from celery import Celery
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared import schemas
from shared.core.config import settings
from shared.db_session import get_async_db_session
from shared.exceptions import ConflictError, InternalError, NotFoundError
from shared.schemas.enums import (
    JobStatusEnum,  # Import XAITypeEnum
    XAIStatusEnum,
    XAITypeEnum,
)

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


class XAIService:
    """
    Facade for managing XAI workflow initiation and status checking.
    """

    def __init__(
        self,
        db: AsyncSession = Depends(get_async_db_session),
        celery_app: Celery = Depends(lambda: backend_celery_app),  # Inject Celery app
    ):
        self.db = db
        self.celery_app = celery_app
        # self.crud_xai = crud.crud_xai_result
        # self.crud_inference = crud.crud_inference_job

    async def trigger_xai_orchestration(self, inference_job_id: int) -> str:
        """
        Validates the inference job and dispatches the XAI orchestration task.

        Returns:
            The Celery task ID for the orchestration task.
        Raises:
            HTTPException: On validation errors or dispatch failures.
        """
        logger.info(
            f"Service: Triggering XAI orchestration for InferenceJob ID: {inference_job_id}"
        )

        # --- Validation ---
        try:
            inference_job = await crud.crud_inference_job.get_inference_job(
                self.db, job_id=inference_job_id
            )
            if not inference_job:
                raise NotFoundError(f"Inference Job {inference_job_id} not found.")
            # Check if prediction was successful before allowing XAI
            if inference_job.status != JobStatusEnum.SUCCESS:
                raise ConflictError(
                    f"Inference job {inference_job_id} is not in SUCCESS state (current: {inference_job.status.value}). Cannot trigger XAI."
                )
        except NotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except ConflictError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e
        except Exception as e:
            logger.error(
                f"Unexpected validation error for XAI trigger: {e}", exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="XAI trigger validation error.",
            ) from e

        # --- Dispatch Orchestration Task ---
        task_name = "tasks.orchestrate_xai"  # Task in ML worker
        args = [inference_job_id]
        try:
            task = self.celery_app.send_task(
                task_name, args=args, queue="ml_queue"
            )  # Use ML queue for orchestrator
            if not task or not task.id:
                raise InternalError(
                    "Celery dispatch returned invalid task object for XAI orchestration."
                )
            task_id = task.id
            logger.info(
                f"Service: Dispatched XAI orchestration task {task_id} for job {inference_job_id}"
            )
            return task_id
        except Exception as e:
            logger.error(
                f"Service: Failed to dispatch Celery task '{task_name}': {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to dispatch XAI orchestration task.",
            ) from e

    async def get_explanation_status(self, xai_result_id: int) -> schemas.XAIResultRead:
        """Gets the combined status (DB + Celery) for a specific XAI result."""
        logger.debug(f"Service: Getting status for XAIResult {xai_result_id}")
        db_xai = await crud.crud_xai_result.get_xai_result(
            self.db, xai_result_id=xai_result_id
        )
        if not db_xai:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"XAI Result {xai_result_id} not found.",
            )

        # Convert DB record to Pydantic schema first
        response_data = schemas.XAIResultRead.model_validate(db_xai)

        # TODO: Fetch and potentially merge Celery task status if needed for more real-time info?
        # For now, relying on the DB status updated by workers.

        return response_data

    async def get_all_explanations_for_job(
        self,
        inference_job_id: int,
        xai_type: Optional[XAITypeEnum] = None,
        status: Optional[XAIStatusEnum] = None,
    ) -> List[schemas.XAIResultRead]:
        """Retrieves all XAI results for a given inference job, with optional filters."""
        logger.debug(
            f"Service: Getting all explanations for InferenceJob {inference_job_id}"
        )
        # Ensure inference job exists (optional, but good practice)
        inference_job = await crud.crud_inference_job.get_inference_job(
            self.db, job_id=inference_job_id
        )
        if not inference_job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inference Job {inference_job_id} not found.",
            )

        results_db = await crud.crud_xai_result.get_xai_results_by_job_id(
            db=self.db,
            inference_job_id=inference_job_id,
            xai_type=xai_type,
            status=status,
        )
        # Convert list of ORM objects to list of Pydantic schemas
        return [schemas.XAIResultRead.model_validate(res) for res in results_db]
