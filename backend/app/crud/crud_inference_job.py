# backend/app/crud/crud_inference_job.py
import logging
from typing import Any, Dict, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.db.models.dataset import Dataset
from shared.db.models.inference_job import InferenceJob
from shared.db.models.ml_model import MLModel
from shared.schemas import InferenceJobCreate
from shared.schemas.enums import JobStatusEnum  # Reuse enum
from shared.schemas.inference_job import InferenceJobUpdate

logger = logging.getLogger(__name__)


async def get_inference_job(db: AsyncSession, job_id: int) -> Optional[InferenceJob]:
    """Get a single inference job by ID."""
    stmt = (
        select(InferenceJob)
        .options(selectinload(InferenceJob.ml_model))
        .filter(InferenceJob.id == job_id)
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_inference_job_by_task_id(
    db: AsyncSession, celery_task_id: str
) -> Optional[InferenceJob]:
    """Get an inference job by its Celery task ID."""
    stmt = (
        select(InferenceJob)
        .options(selectinload(InferenceJob.ml_model))
        .filter(InferenceJob.celery_task_id == celery_task_id)
    )
    result = await db.execute(stmt)
    # Task ID might not be unique if retried, maybe fetch latest?
    return result.scalars().first()  # Return first match for now


async def get_inference_jobs(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    model_id: Optional[int] = None,
    status: Optional[JobStatusEnum] = None,
) -> Sequence[InferenceJob]:
    """Get multiple inference jobs with optional filtering and pagination."""
    stmt = select(InferenceJob).order_by(InferenceJob.created_at.desc())
    if model_id is not None:
        stmt = stmt.filter(InferenceJob.ml_model_id == model_id)
    if status:
        stmt = stmt.filter(InferenceJob.status == status)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


async def create_inference_job(
    db: AsyncSession, *, obj_in: InferenceJobCreate
) -> InferenceJob:
    """Create a new inference job record."""
    # Note: obj_in should be InferenceJobCreateInternal type here based on import alias
    db_obj = InferenceJob(
        ml_model_id=obj_in.ml_model_id,
        input_reference=obj_in.input_reference,  # Already a dict
        status=obj_in.status,  # Status passed in
        celery_task_id=obj_in.celery_task_id,  # Initial task ID passed in
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    logger.info(f"Created Inference Job ID {db_obj.id} for model {db_obj.ml_model_id}")
    return db_obj


async def update_inference_job(
    db: AsyncSession,
    *,
    db_obj: InferenceJob,
    obj_in: InferenceJobUpdate | Dict[str, Any],
) -> InferenceJob:
    """Update an existing inference job record."""
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(db_obj, field, value)

    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    # Eager load the relationship again after refresh
    await db.refresh(db_obj, attribute_names=["ml_model"])
    logger.info(f"Updated Inference Job ID {db_obj.id}, Status: {db_obj.status.value}")
    return db_obj


async def delete_inference_job(
    db: AsyncSession, *, job_id: int
) -> Optional[InferenceJob]:
    """Delete an inference job record."""
    db_obj = await get_inference_job(db, job_id)
    if db_obj:
        await db.delete(db_obj)
        await db.commit()
        logger.info(f"Deleted Inference Job ID {job_id}")
    return db_obj

async def get_inference_jobs_by_repository(db: AsyncSession, *, repository_id: int, skip: int = 0, limit: int = 100) -> Sequence[InferenceJob]:
    dataset_ids_stmt = select(Dataset.id).where(Dataset.repository_id == repository_id)
    model_ids_stmt = select(MLModel.id).where(MLModel.dataset_id.in_(dataset_ids_stmt))
    
    stmt = (
        select(InferenceJob)
        .options(selectinload(InferenceJob.ml_model)) # Eager load
        .where(InferenceJob.ml_model_id.in_(model_ids_stmt))
        .order_by(InferenceJob.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()
