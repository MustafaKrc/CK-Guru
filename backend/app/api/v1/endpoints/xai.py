# backend/app/api/v1/endpoints/xai.py
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

# Import CRUD, Schemas, DB session
from app import crud
from shared.schemas import XAIResultRead
from shared.schemas.enums import XAITypeEnum, XAIStatusEnum
from shared.db_session import get_async_db_session
from shared.core.config import settings # May not be needed directly

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

router = APIRouter()

@router.get(
    "/infer/{job_id}/explanations",
    response_model=List[XAIResultRead],
    summary="Get All Explanation Results for an Inference Job",
    description="Retrieves the status and results (if available) for all requested XAI techniques associated with a specific inference job.",
    responses={
        404: {"description": "Inference job not found (implicitly, as no explanations would exist)"},
    }
)
async def get_inference_explanations(
    job_id: int,
    db: AsyncSession = Depends(get_async_db_session),
    # Add filters? e.g., ?type=shap or ?status=success
    xai_type: Optional[XAITypeEnum] = Query(None, description="Filter by explanation type"),
    status: Optional[XAIStatusEnum] = Query(None, description="Filter by explanation status"),
):
    """Retrieve all XAI results linked to a given inference job ID."""
    # Optional: Check if inference job itself exists first?
    # inference_job = await crud.crud_inference_job.get_inference_job(db, job_id)
    # if not inference_job:
    #     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Inference Job {job_id} not found")

    xai_results = await crud.crud_xai_result.get_xai_results_by_job_id(
        db=db, inference_job_id=job_id, xai_type=xai_type, status=status
    )
    # Pydantic handles ORM to Schema conversion
    return xai_results


@router.get(
    "/xai/{xai_result_id}",
    response_model=XAIResultRead,
    summary="Get Specific Explanation Result",
    description="Retrieves the details, status, and result data for a single XAI generation job.",
    responses={404: {"description": "XAI Result not found"}},
)
async def get_specific_explanation(
    xai_result_id: int,
    db: AsyncSession = Depends(get_async_db_session),
):
    """Retrieve details for a single XAI result by its unique ID."""
    db_xai_result = await crud.crud_xai_result.get_xai_result(db, xai_result_id=xai_result_id)
    if db_xai_result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="XAI Result not found")
    return db_xai_result

# Note: No POST/PUT/DELETE endpoints for XAI results as they are typically created/updated by the inference job process