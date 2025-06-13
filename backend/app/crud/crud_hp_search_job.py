# backend/app/crud/crud_hp_search_job.py
import logging
from typing import Any, Dict, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.db.models.dataset import Dataset
from shared.db.models.hp_search_job import HyperparameterSearchJob
from shared.db.models.ml_model import MLModel # Ensure MLModel is imported for selectinload path
from shared.db.models.training_job import JobStatusEnum  # Reuse enum
from shared.schemas.hp_search_job import HPSearchJobCreate, HPSearchJobUpdate

logger = logging.getLogger(__name__)


async def get_hp_search_job(
    db: AsyncSession, job_id: int
) -> Optional[HyperparameterSearchJob]:
    """Get a single HP search job by ID."""
    stmt = (
        select(HyperparameterSearchJob)
        .options(selectinload(HyperparameterSearchJob.best_ml_model))
        .filter(HyperparameterSearchJob.id == job_id)
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_hp_search_job_by_task_id(
    db: AsyncSession, celery_task_id: str
) -> Optional[HyperparameterSearchJob]:
    """Get an HP search job by its Celery task ID."""
    stmt = (
        select(HyperparameterSearchJob)
        .options(selectinload(HyperparameterSearchJob.best_ml_model))
        .filter(HyperparameterSearchJob.celery_task_id == celery_task_id)
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_hp_search_jobs(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    dataset_id: Optional[int] = None,
    status: Optional[JobStatusEnum] = None,
    study_name: Optional[str] = None,
) -> Tuple[Sequence[HyperparameterSearchJob], int]:  # Return tuple
    """Get multiple HP search jobs with optional filtering and pagination."""
    stmt_items = (
        select(HyperparameterSearchJob)
        .options(
            selectinload(HyperparameterSearchJob.best_ml_model)
            .selectinload(MLModel.dataset)
            .selectinload(Dataset.repository)  # Eager load repository
        )
        .order_by(HyperparameterSearchJob.created_at.desc())
    )
    filters = []
    if dataset_id is not None:
        filters.append(HyperparameterSearchJob.dataset_id == dataset_id)
    if status:
        filters.append(HyperparameterSearchJob.status == status)
    if study_name:
        filters.append(
            HyperparameterSearchJob.optuna_study_name.ilike(f"%{study_name}%")
        )  # Added ilike for partial match

    if filters:
        stmt_items = stmt_items.where(*filters)

    stmt_total = select(func.count(HyperparameterSearchJob.id))
    if filters:
        stmt_total = stmt_total.where(*filters)

    result_total = await db.execute(stmt_total)
    total = result_total.scalar_one_or_none() or 0

    stmt_items = stmt_items.offset(skip).limit(limit)
    result_items = await db.execute(stmt_items)
    items = result_items.scalars().all()

    return items, total


async def create_hp_search_job(
    db: AsyncSession, *, obj_in: HPSearchJobCreate
) -> HyperparameterSearchJob:
    """Create a new HP search job record."""
    db_obj = HyperparameterSearchJob(
        dataset_id=obj_in.dataset_id,
        optuna_study_name=obj_in.optuna_study_name,
        config=obj_in.config.model_dump(),
        status=JobStatusEnum.PENDING,
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    logger.info(
        f"Created HP Search Job ID {db_obj.id} (Study: {db_obj.optuna_study_name})"
    )
    return db_obj


async def update_hp_search_job(
    db: AsyncSession,
    *,
    db_obj: HyperparameterSearchJob,
    obj_in: HPSearchJobUpdate | Dict[str, Any],
) -> HyperparameterSearchJob:
    """Update an existing HP search job record."""
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
    await db.refresh(db_obj, attribute_names=["best_ml_model"])
    logger.info(f"Updated HP Search Job ID {db_obj.id}, Status: {db_obj.status.value}")
    return db_obj


async def delete_hp_search_job(
    db: AsyncSession, *, job_id: int
) -> Optional[HyperparameterSearchJob]:
    """Delete an HP search job record."""
    # Consider Optuna study cleanup? Optuna usually manages its own tables.
    db_obj = await get_hp_search_job(db, job_id)
    if db_obj:
        await db.delete(db_obj)
        await db.commit()
        logger.info(f"Deleted HP Search Job ID {job_id}")
    return db_obj


async def get_hp_search_jobs_by_repository(
    db: AsyncSession, *, repository_id: int, skip: int = 0, limit: int = 100
) -> Tuple[Sequence[HyperparameterSearchJob], int]:
    """Get HP search jobs for a repository with pagination and total count."""
    dataset_ids_stmt = select(Dataset.id).where(Dataset.repository_id == repository_id)

    # Query for items
    stmt_items = (
        select(HyperparameterSearchJob)
        .options(selectinload(HyperparameterSearchJob.best_ml_model))  # Eager load
        .where(HyperparameterSearchJob.dataset_id.in_(dataset_ids_stmt))
        .order_by(HyperparameterSearchJob.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result_items = await db.execute(stmt_items)
    items = result_items.scalars().all()

    # Query for total count
    stmt_total = select(func.count(HyperparameterSearchJob.id)).where(
        HyperparameterSearchJob.dataset_id.in_(dataset_ids_stmt)
    )
    result_total = await db.execute(stmt_total)
    total = result_total.scalar_one_or_none() or 0

    return items, total
