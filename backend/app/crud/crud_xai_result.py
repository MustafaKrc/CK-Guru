# backend/app/crud/crud_xai_result.py
import logging
from typing import Any, Dict, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Import models and schemas
from shared.db.models.xai_result import XAIResult
from shared.schemas.enums import XAIStatusEnum, XAITypeEnum
from shared.schemas.xai_job import XAIResultCreate, XAIResultUpdate

logger = logging.getLogger(__name__)


async def get_xai_result(db: AsyncSession, xai_result_id: int) -> Optional[XAIResult]:
    """Get a single XAI result by ID."""
    result = await db.execute(select(XAIResult).filter(XAIResult.id == xai_result_id))
    return result.scalars().first()


async def get_xai_results_by_job_id(
    db: AsyncSession,
    *,
    inference_job_id: int,
    xai_type: Optional[XAITypeEnum] = None,  # Optional filter by type
    status: Optional[XAIStatusEnum] = None,  # Optional filter by status
) -> Sequence[XAIResult]:
    """Get XAI results associated with a specific inference job."""
    stmt = select(XAIResult).filter(XAIResult.inference_job_id == inference_job_id)
    if xai_type:
        stmt = stmt.filter(XAIResult.xai_type == xai_type)
    if status:
        stmt = stmt.filter(XAIResult.status == status)
    stmt = stmt.order_by(XAIResult.created_at.asc())  # Order by creation time
    result = await db.execute(stmt)
    return result.scalars().all()


async def create_xai_result(db: AsyncSession, *, obj_in: XAIResultCreate) -> XAIResult:
    """Create a new XAI result record (typically in PENDING state)."""
    # Pydantic model handles default status
    db_obj = XAIResult(**obj_in.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    logger.info(
        f"Created XAIResult ID {db_obj.id} for Job {db_obj.inference_job_id}, Type: {db_obj.xai_type.value}"
    )
    return db_obj


async def update_xai_result(
    db: AsyncSession, *, db_obj: XAIResult, obj_in: XAIResultUpdate | Dict[str, Any]
) -> XAIResult:
    """Update an existing XAI result record (status, results, etc.)."""
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(db_obj, field, value)

    db.add(db_obj)  # Add modified object to session
    await db.commit()
    await db.refresh(db_obj)
    logger.info(f"Updated XAIResult ID {db_obj.id}, Status: {db_obj.status.value}")
    return db_obj


async def delete_xai_result(
    db: AsyncSession, *, xai_result_id: int
) -> Optional[XAIResult]:
    """Delete an XAI result record."""
    db_obj = await get_xai_result(db, xai_result_id)
    if db_obj:
        job_id = db_obj.inference_job_id
        xai_type = db_obj.xai_type.value
        await db.delete(db_obj)
        await db.commit()
        logger.info(
            f"Deleted XAIResult ID {xai_result_id} (Job: {job_id}, Type: {xai_type})"
        )
    return db_obj
