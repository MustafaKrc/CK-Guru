# backend/app/crud/crud_training_job.py
import logging
from typing import Any, Dict, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.db.models.dataset import Dataset
from shared.db.models.ml_model import MLModel # Ensure MLModel is imported for selectinload path
from shared.db.models.training_job import JobStatusEnum, TrainingJob
from shared.schemas.training_job import TrainingJobCreate, TrainingJobUpdate

logger = logging.getLogger(__name__)


async def get_training_job(db: AsyncSession, job_id: int) -> Optional[TrainingJob]:
    """Get a single training job by ID, optionally loading the related model."""
    stmt = (
        select(TrainingJob)
        .options(selectinload(TrainingJob.ml_model))
        .filter(TrainingJob.id == job_id)
    )  # Eager loading
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_training_job_by_task_id(
    db: AsyncSession, celery_task_id: str
) -> Optional[TrainingJob]:
    """Get a training job by its Celery task ID."""
    stmt = (
        select(TrainingJob)
        .options(selectinload(TrainingJob.ml_model))
        .filter(TrainingJob.celery_task_id == celery_task_id)
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_training_jobs(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    dataset_id: Optional[int] = None,
    status: Optional[JobStatusEnum] = None,
) -> Tuple[Sequence[TrainingJob], int]:  # Return tuple
    """Get multiple training jobs with optional filtering and pagination."""
    stmt_items = (
        select(TrainingJob)
        .options(
            selectinload(TrainingJob.ml_model)
            .selectinload(MLModel.dataset)
            .selectinload(Dataset.repository)  # Eager load repository
        )
        .order_by(TrainingJob.created_at.desc())
    )
    filters = []
    if dataset_id is not None:
        filters.append(TrainingJob.dataset_id == dataset_id)
    if status:
        filters.append(TrainingJob.status == status)

    if filters:
        stmt_items = stmt_items.where(*filters)

    stmt_total = select(func.count(TrainingJob.id))
    if filters:
        stmt_total = stmt_total.where(*filters)

    result_total = await db.execute(stmt_total)
    total = result_total.scalar_one_or_none() or 0

    stmt_items = stmt_items.offset(skip).limit(limit)
    result_items = await db.execute(stmt_items)
    items = result_items.scalars().all()

    return items, total


async def create_training_job(
    db: AsyncSession, *, obj_in: TrainingJobCreate
) -> TrainingJob:
    """Create a new training job record."""
    db_obj = TrainingJob(
        dataset_id=obj_in.dataset_id,
        config=obj_in.config.model_dump(),  # Store config as dict
        status=JobStatusEnum.PENDING,  # Initial status
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
    await db.refresh(db_obj, attribute_names=["ml_model"])
    logger.info(f"Updated Training Job ID {db_obj.id}, Status: {db_obj.status.value}")
    return db_obj


async def delete_training_job(
    db: AsyncSession, *, job_id: int
) -> Optional[TrainingJob]:
    """Delete a training job record."""
    # Consider implications: Does deleting the job delete the model? (Current FK is SET NULL)
    db_obj = await get_training_job(db, job_id)
    if db_obj:
        await db.delete(db_obj)
        await db.commit()
        logger.info(f"Deleted Training Job ID {job_id}")
    return db_obj


async def get_training_jobs_by_repository(
    db: AsyncSession, *, repository_id: int, skip: int = 0, limit: int = 100
) -> Tuple[Sequence[TrainingJob], int]:
    """Get training jobs for a repository with pagination and total count."""
    dataset_ids_stmt = select(Dataset.id).where(Dataset.repository_id == repository_id)

    # Query for items
    stmt_items = (
        select(TrainingJob)
        .options(selectinload(TrainingJob.ml_model))  # Eager load related model
        .where(TrainingJob.dataset_id.in_(dataset_ids_stmt))
        .order_by(TrainingJob.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result_items = await db.execute(stmt_items)
    items = result_items.scalars().all()

    # Query for total count
    stmt_total = select(func.count(TrainingJob.id)).where(
        TrainingJob.dataset_id.in_(dataset_ids_stmt)
    )
    result_total = await db.execute(stmt_total)
    total = result_total.scalar_one_or_none() or 0

    return items, total
