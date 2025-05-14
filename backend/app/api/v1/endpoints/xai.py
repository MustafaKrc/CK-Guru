# backend/app/api/v1/endpoints/xai.py
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query

# Import CRUD, Schemas, DB session
from app.services.xai_service import XAIService
from shared import schemas  # Import root schemas
from shared.core.config import settings
from shared.schemas.enums import XAIStatusEnum, XAITypeEnum

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

router = APIRouter()


@router.get(
    "/infer/{job_id}/explanations",
    response_model=List[schemas.XAIResultRead],  # Use schemas prefix
    summary="Get All Explanation Results for an Inference Job",
    description="Retrieves the status and results (if available) for all XAI techniques associated with a specific inference job.",
    responses={
        404: {"description": "Inference job not found"},
    },
)
async def get_inference_explanations(
    job_id: int,
    xai_service: XAIService = Depends(XAIService),  # Inject service
    # Add filters? e.g., ?type=shap or ?status=success
    xai_type: Optional[XAITypeEnum] = Query(
        None, description="Filter by explanation type"
    ),
    status: Optional[XAIStatusEnum] = Query(
        None, description="Filter by explanation status"
    ),
):
    """Retrieve all XAI results linked to a given inference job ID using the XAIService."""
    # Service handles validation of inference job existence implicitly
    return await xai_service.get_all_explanations_for_job(
        inference_job_id=job_id, xai_type=xai_type, status=status
    )


@router.get(
    "/explanations/{xai_result_id}",  # Changed path prefix to avoid clash
    response_model=schemas.XAIResultRead,  # Use schemas prefix
    summary="Get Specific Explanation Result",
    description="Retrieves the details, status, and result data for a single XAI generation job.",
    responses={404: {"description": "XAI Result not found"}},
)
async def get_specific_explanation(
    xai_result_id: int,
    xai_service: XAIService = Depends(XAIService),  # Inject service
):
    """Retrieve details for a single XAI result by its unique ID using the XAIService."""
    return await xai_service.get_explanation_status(xai_result_id=xai_result_id)


# Note: No POST/PUT/DELETE endpoints for XAI results as they are managed via the orchestration trigger
