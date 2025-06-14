# backend/app/crud/crud_hp_search_job.py
import logging
from typing import Any, Dict, Optional, Sequence, Tuple

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.db.models.dataset import Dataset
from shared.db.models.hp_search_job import HyperparameterSearchJob
from shared.db.models.ml_model import MLModel
from shared.db.models.repository import Repository  # Added import
from shared.db.models.training_job import JobStatusEnum  # Reuse enum
from shared.schemas.hp_search_job import HPSearchJobCreate, HPSearchJobUpdate

logger = logging.getLogger(__name__)


async def get_hp_search_job(
    db: AsyncSession, job_id: int
) -> Optional[HyperparameterSearchJob]:
    """Get a single HP search job by ID."""
    stmt = (
        select(HyperparameterSearchJob)
        .options(
            selectinload(HyperparameterSearchJob.dataset).selectinload(
                Dataset.repository
            ),
            selectinload(HyperparameterSearchJob.best_ml_model)
            .selectinload(MLModel.dataset)
            .selectinload(Dataset.repository),
        )
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
        .options(
            selectinload(HyperparameterSearchJob.dataset).selectinload(
                Dataset.repository
            ),
            selectinload(HyperparameterSearchJob.best_ml_model)
            .selectinload(MLModel.dataset)
            .selectinload(Dataset.repository),
        )
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
    name_filter: Optional[str] = None,
    repository_id: Optional[int] = None,
    sort_by: Optional[str] = "created_at",
    sort_dir: Optional[str] = "desc",
) -> Tuple[Sequence[HyperparameterSearchJob], int]:
    """Get multiple HP search jobs with optional filtering and pagination."""
    stmt_items = select(HyperparameterSearchJob).options(
        selectinload(HyperparameterSearchJob.dataset).selectinload(Dataset.repository),
        selectinload(HyperparameterSearchJob.best_ml_model)
        .selectinload(
            MLModel.dataset
        )  # Ensure full chain for best_ml_model if needed elsewhere
        .selectinload(Dataset.repository),
    )
    stmt_total = select(func.count(HyperparameterSearchJob.id))

    # Determine required joins for filtering and sorting
    needs_dataset_join = False
    needs_repository_join = False

    if repository_id is not None:
        needs_dataset_join = True

    if sort_by == "repository_name":
        needs_dataset_join = True
        needs_repository_join = True
    elif sort_by == "dataset_name":
        needs_dataset_join = True
    # Note: 'model_type' sort uses HyperparameterSearchJob.config, no extra join needed for it.

    # Apply joins
    if needs_dataset_join:
        stmt_items = stmt_items.join(
            Dataset, HyperparameterSearchJob.dataset_id == Dataset.id
        )
        stmt_total = stmt_total.join(
            Dataset, HyperparameterSearchJob.dataset_id == Dataset.id
        )
    if needs_repository_join:  # Assumes Dataset is already joined
        stmt_items = stmt_items.join(Repository, Dataset.repository_id == Repository.id)
        stmt_total = stmt_total.join(Repository, Dataset.repository_id == Repository.id)

    filters = []
    if dataset_id is not None:
        filters.append(HyperparameterSearchJob.dataset_id == dataset_id)
    if status:
        filters.append(HyperparameterSearchJob.status == status)
    if name_filter:
        filters.append(
            HyperparameterSearchJob.optuna_study_name.ilike(f"%{name_filter}%")
        )
    if repository_id is not None:
        filters.append(Dataset.repository_id == repository_id)

    if filters:
        stmt_items = stmt_items.where(*filters)
        stmt_total = stmt_total.where(*filters)

    result_total = await db.execute(stmt_total)
    total = result_total.scalar_one_or_none() or 0

    sort_mapping = {
        "name": HyperparameterSearchJob.optuna_study_name,
        "status": HyperparameterSearchJob.status,
        "created_at": HyperparameterSearchJob.created_at,
        "repository_name": Repository.name,
        "dataset_name": Dataset.name,
        "model_type": HyperparameterSearchJob.config.op("->>")("model_type"),
    }
    sort_column = sort_mapping.get(sort_by, HyperparameterSearchJob.created_at)

    stmt_items = stmt_items.order_by(
        desc(sort_column) if sort_dir == "desc" else asc(sort_column)
    )

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
    # Eager load the relationship chain again after refresh
    await db.refresh(db_obj, attribute_names=["best_ml_model", "dataset"])
    if db_obj.best_ml_model:
        await db.refresh(db_obj.best_ml_model, attribute_names=["dataset"])
        if db_obj.best_ml_model.dataset:
            await db.refresh(
                db_obj.best_ml_model.dataset, attribute_names=["repository"]
            )
    if db_obj.dataset:
        await db.refresh(db_obj.dataset, attribute_names=["repository"])
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
        .options(
            selectinload(HyperparameterSearchJob.best_ml_model)
            .selectinload(MLModel.dataset)
            .selectinload(Dataset.repository),  # Eager load repository
            selectinload(HyperparameterSearchJob.dataset).selectinload(
                Dataset.repository
            ),
        )
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
