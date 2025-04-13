# backend/app/crud/crud_training_job.py
import logging
from typing import Optional, Sequence, Dict, Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models.training_job import TrainingJob, JobStatusEnum
from shared.schemas.training_job import TrainingJobCreate, TrainingJobUpdate

logger = logging.getLogger(__name__)

async def get_training_job(db: AsyncSession, job_id: int) -> Optional[TrainingJob]:
    """Get a single training job by ID, optionally loading the related model."""
    stmt = select(TrainingJob).options(selectinload(TrainingJob.ml_model)).filter(TrainingJob.id == job_id) # Eager loading
    result = await db.execute(stmt)
    return result.scalars().first()

async def get_training_job_by_task_id(db: AsyncSession, celery_task_id: str) -> Optional[TrainingJob]:
    """Get a training job by its Celery task ID."""
    stmt = select(TrainingJob).options(selectinload(TrainingJob.ml_model)).filter(TrainingJob.celery_task_id == celery_task_id)
    result = await db.execute(stmt)
    return result.scalars().first()

async def get_training_jobs(
    db: AsyncSession, *, skip: int = 0, limit: int = 100,
    dataset_id: Optional[int] = None, status: Optional[JobStatusEnum] = None
) -> Sequence[TrainingJob]:
    """Get multiple training jobs with optional filtering and pagination."""
    stmt = (select(TrainingJob)
        .options(selectinload(TrainingJob.ml_model)) # Eager load
        .order_by(TrainingJob.created_at.desc()))
    if dataset_id is not None:
        stmt = stmt.filter(TrainingJob.dataset_id == dataset_id)
    if status:
        stmt = stmt.filter(TrainingJob.status == status)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

async def create_training_job(db: AsyncSession, *, obj_in: TrainingJobCreate) -> TrainingJob:
    """Create a new training job record."""
    db_obj = TrainingJob(
        dataset_id=obj_in.dataset_id,
        config=obj_in.config.model_dump(), # Store config as dict
        status=JobStatusEnum.PENDING # Initial status
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    logger.info(f"Created Training Job ID {db_obj.id} for dataset {db_obj.dataset_id}")
    return db_obj

async def update_training_job(
    db: AsyncSession, *, db_obj: TrainingJob, obj_in: TrainingJobUpdate | Dict[str, Any]
) -> TrainingJob:
    """Update an existing training job record."""
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(db_obj, field, value)

    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    # Eager load the relationship again after refresh if it was loaded before
    await db.refresh(db_obj, attribute_names=['ml_model'])
    logger.info(f"Updated Training Job ID {db_obj.id}, Status: {db_obj.status.value}")
    return db_obj

async def delete_training_job(db: AsyncSession, *, job_id: int) -> Optional[TrainingJob]:
    """Delete a training job record."""
    # Consider implications: Does deleting the job delete the model? (Current FK is SET NULL)
    db_obj = await get_training_job(db, job_id)
    if db_obj:
        await db.delete(db_obj)
        await db.commit()
        logger.info(f"Deleted Training Job ID {job_id}")
    return db_obj