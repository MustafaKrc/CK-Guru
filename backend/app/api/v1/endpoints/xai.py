# backend/app/api/v1/endpoints/xai.py
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.services.xai_service import XAIService
from shared.schemas.xai_job import XAIResultRead, XAITriggerResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/inference-jobs/{inference_job_id}/xai-results",
    response_model=List[XAIResultRead],
    summary="Get all XAI results for an inference job",
    description="Retrieves all XAI (Explainable AI) results associated with a specific inference job, with optional filters for XAI type and status.",
)
async def get_all_xai_results_for_job(
    inference_job_id: int,
    # TODO: Add xai_type: Optional[XAITypeEnum] = None, status: Optional[XAIStatusEnum] = None as query params
    xai_service: XAIService = Depends(XAIService),
):
    """
    Endpoint to retrieve all XAI results for a given inference job.
    """
    logger.info(f"API: Getting all XAI results for InferenceJob ID: {inference_job_id}")
    try:
        # For now, not passing xai_type or status, but the service supports them
        results = await xai_service.get_all_explanations_for_job(
            inference_job_id=inference_job_id
        )
        if not results:
            # Depending on desired behavior, this might not be an error,
            # but an empty list. If job must exist, service handles NotFoundError.
            logger.info(
                f"API: No XAI results found for InferenceJob ID: {inference_job_id}"
            )
        return results
    except HTTPException:
        # Re-raise HTTPException directly if service raised it (e.g., 404 for inference job)
        raise
    except Exception as e:
        logger.error(
            f"API: Unexpected error getting XAI results for job {inference_job_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving XAI results.",
        )


@router.post(
    "/inference-jobs/{inference_job_id}/xai-results/trigger",
    response_model=XAITriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger XAI orchestration for an inference job",
    description="Triggers the XAI orchestration process for a completed and successful inference job.",
)
async def trigger_xai_for_job(
    inference_job_id: int,
    xai_service: XAIService = Depends(XAIService),
):
    """
    Endpoint to trigger XAI orchestration for a specific inference job.
    """
    logger.info(f"API: Triggering XAI for InferenceJob ID: {inference_job_id}")
    try:
        task_id = await xai_service.trigger_xai_orchestration(
            inference_job_id=inference_job_id
        )
        return XAITriggerResponse(
            task_id=task_id,
            message="XAI orchestration triggered successfully.",
        )
    except HTTPException:
        # Re-raise HTTPException directly (e.g., 404, 409 from service)
        raise
    except Exception as e:
        logger.error(
            f"API: Unexpected error triggering XAI for job {inference_job_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while triggering XAI.",
        )
