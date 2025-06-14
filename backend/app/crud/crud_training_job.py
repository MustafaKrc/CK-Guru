# backend/app/crud/crud_training_job.py
import logging
from typing import Any, Dict, Optional, Sequence, Tuple

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.db.models.dataset import Dataset
from shared.db.models.ml_model import MLModel
from shared.db.models.repository import Repository  # Added import
from shared.db.models.training_job import JobStatusEnum, TrainingJob
from shared.schemas.training_job import TrainingJobCreate, TrainingJobUpdate

logger = logging.getLogger(__name__)


async def get_training_job(db: AsyncSession, job_id: int) -> Optional[TrainingJob]:
    """Get a single training job by ID, optionally loading the related model."""
    stmt = (
        select(TrainingJob)
        .options(
            selectinload(TrainingJob.dataset).selectinload(Dataset.repository),
            selectinload(TrainingJob.ml_model)
            .selectinload(MLModel.dataset)
            .selectinload(Dataset.repository),
        )
        .filter(TrainingJob.id == job_id)
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_training_job_by_task_id(
    db: AsyncSession, celery_task_id: str
) -> Optional[TrainingJob]:
    """Get a training job by its Celery task ID."""
    stmt = (
        select(TrainingJob)
        .options(
            selectinload(TrainingJob.dataset).selectinload(Dataset.repository),
            selectinload(TrainingJob.ml_model)
            .selectinload(MLModel.dataset)
            .selectinload(Dataset.repository),
        )
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
    repository_id: Optional[int] = None,
    status: Optional[JobStatusEnum] = None,
    name_filter: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    sort_dir: Optional[str] = "desc",
) -> Tuple[Sequence[TrainingJob], int]:
    """Get multiple training jobs with optional filtering and pagination."""

    stmt_items = select(TrainingJob).options(
        selectinload(TrainingJob.dataset).selectinload(Dataset.repository),
        selectinload(TrainingJob.ml_model)
        # Eager load ml_model.dataset.repository if needed for response serialization
        .selectinload(MLModel.dataset).selectinload(Dataset.repository),
    )
    stmt_total = select(func.count(TrainingJob.id))

    # Determine required joins based on filters and sorting
    needs_dataset_join = False
    needs_repository_join = False  # For joining Repository table via Dataset

    if repository_id is not None:
        needs_dataset_join = True  # Filtering by repository_id requires joining Dataset

    if sort_by == "dataset_name":
        needs_dataset_join = True
    elif sort_by == "repository_name":
        needs_dataset_join = True
        needs_repository_join = True

    # Apply joins
    # Join Dataset if needed for filtering by repository_id or sorting by dataset_name/repository_name
    if needs_dataset_join:
        stmt_items = stmt_items.join(TrainingJob.dataset.of_type(Dataset))
        stmt_total = stmt_total.join(TrainingJob.dataset.of_type(Dataset))

        # If repository_name sort or repository_id filter, further join Repository
        if needs_repository_join:  # This implies Dataset was already joined
            stmt_items = stmt_items.join(Dataset.repository.of_type(Repository))
            stmt_total = stmt_total.join(Dataset.repository.of_type(Repository))

    filters = []
    if dataset_id is not None:
        filters.append(TrainingJob.dataset_id == dataset_id)
    if repository_id is not None:
        # This filter now assumes Dataset table is already joined if repository_id is present
        filters.append(Dataset.repository_id == repository_id)
    if status:
        filters.append(TrainingJob.status == status)
    if name_filter:
        filters.append(
            TrainingJob.config.op("->>")("model_name").ilike(f"%{name_filter}%")
        )

    if filters:
        stmt_items = stmt_items.where(*filters)
        stmt_total = stmt_total.where(*filters)

    # Get total count
    result_total = await db.execute(stmt_total)
    total = result_total.scalar_one_or_none() or 0

    # Sorting
    sort_mapping = {
        "name": TrainingJob.config.op("->>")("model_name"),
        "status": TrainingJob.status,
        "created_at": TrainingJob.created_at,
        "repository_name": Repository.name,  # Requires Repository join
        "dataset_name": Dataset.name,  # Requires Dataset join
        "model_type": TrainingJob.config.op("->>")("model_type"),
    }
    sort_column = sort_mapping.get(sort_by, TrainingJob.created_at)

    stmt_items = stmt_items.order_by(
        desc(sort_column) if sort_dir == "desc" else asc(sort_column)
    )

    # Pagination
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
    # Eager load the relationship chain again after refresh
    await db.refresh(db_obj, attribute_names=["ml_model", "dataset"])
    if db_obj.ml_model and db_obj.ml_model.dataset:
        await db.refresh(db_obj.ml_model.dataset, attribute_names=["repository"])
    if db_obj.dataset:
        await db.refresh(db_obj.dataset, attribute_names=["repository"])

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
        .options(
            selectinload(TrainingJob.dataset).selectinload(Dataset.repository),
            selectinload(TrainingJob.ml_model)
            .selectinload(MLModel.dataset)
            .selectinload(Dataset.repository),
        )
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
