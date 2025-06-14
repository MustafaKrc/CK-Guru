# backend/app/crud/crud_inference_job.py
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import asc, desc, func, select, cast
from sqlalchemy.types import Integer as SAInteger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.db.models.dataset import Dataset
from shared.db.models.inference_job import InferenceJob
from shared.db.models.ml_model import MLModel
from shared.db.models.repository import Repository
from shared.schemas import InferenceJobCreate
from shared.schemas.enums import JobStatusEnum
from shared.schemas.inference_job import InferenceJobUpdate

logger = logging.getLogger(__name__)


async def get_inference_job(db: AsyncSession, job_id: int) -> Optional[InferenceJob]:
    """Get a single inference job by ID."""
    stmt = (
        select(InferenceJob)
        .options(
            selectinload(InferenceJob.ml_model)
            .selectinload(MLModel.dataset)
            .selectinload(Dataset.repository)
        )
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
        .options(
            selectinload(InferenceJob.ml_model)
            .selectinload(MLModel.dataset)
            .selectinload(Dataset.repository)
        )
        .filter(InferenceJob.celery_task_id == celery_task_id)
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_inference_jobs(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    model_id: Optional[int] = None,
    status: Optional[JobStatusEnum] = None,
    name_filter: Optional[str] = None,  # For commit hash
    repository_id: Optional[int] = None,
    sort_by: Optional[str] = "created_at",
    sort_dir: Optional[str] = "desc",
) -> Tuple[Sequence[InferenceJob], int]:
    """Get multiple inference jobs with optional filtering, joining, and sorting."""
    stmt_items = select(InferenceJob).options(
        selectinload(InferenceJob.ml_model)
        .selectinload(MLModel.dataset)
        .selectinload(Dataset.repository)
    )
    stmt_total = select(func.count(InferenceJob.id))

    # --- Conditional Joins ---
    # Join necessary tables if filtering or sorting on their fields
    needs_ml_model_join = False
    needs_dataset_join = False
    needs_repository_join = False

    # Check for repository filter or sorting by repository/model name
    if repository_id is not None or sort_by in ["repository_name", "model_name"]:
        needs_ml_model_join = True
        needs_dataset_join = True
        if sort_by == "repository_name":
            needs_repository_join = True

    if needs_ml_model_join:
        stmt_items = stmt_items.join(MLModel, InferenceJob.ml_model_id == MLModel.id)
        stmt_total = stmt_total.join(MLModel, InferenceJob.ml_model_id == MLModel.id)
    if needs_dataset_join:
        stmt_items = stmt_items.join(Dataset, MLModel.dataset_id == Dataset.id)
        stmt_total = stmt_total.join(Dataset, MLModel.dataset_id == Dataset.id)
    if needs_repository_join:
        stmt_items = stmt_items.join(Repository, Dataset.repository_id == Repository.id)
        stmt_total = stmt_total.join(Repository, Dataset.repository_id == Repository.id)

    # --- Build Filters ---
    filters = []
    if model_id is not None:
        filters.append(InferenceJob.ml_model_id == model_id)
    if status:
        filters.append(InferenceJob.status == status)
    if name_filter:
        filters.append(
            InferenceJob.input_reference.op("->>")("commit_hash").ilike(
                f"%{name_filter}%"
            )
        )
    if repository_id is not None:
        filters.append(Dataset.repository_id == repository_id)

    if filters:
        stmt_items = stmt_items.where(*filters)
        stmt_total = stmt_total.where(*filters)

    # --- Get Total Count ---
    result_total = await db.execute(stmt_total)
    total = result_total.scalar_one_or_none() or 0

    # --- Apply Sorting ---
    sort_mapping = {
        "job_id": InferenceJob.id,
        "status": InferenceJob.status,
        "triggered_at": InferenceJob.created_at,
        "repository_name": Repository.name,
        "model_name": MLModel.name,
        "commit": InferenceJob.input_reference.op("->>")("commit_hash"),
        "prediction": cast(
            InferenceJob.prediction_result.op("->>")("commit_prediction"), SAInteger
        ),
    }

    sort_column = sort_mapping.get(sort_by, InferenceJob.created_at)

    stmt_items = stmt_items.order_by(
        desc(sort_column) if sort_dir == "desc" else asc(sort_column)
    )

    stmt_items = stmt_items.offset(skip).limit(limit)
    result_items = await db.execute(stmt_items)
    items = result_items.scalars().all()

    return items, total


async def create_inference_job(
    db: AsyncSession, *, obj_in: InferenceJobCreate
) -> InferenceJob:
    """Create a new inference job record."""
    db_obj = InferenceJob(
        ml_model_id=obj_in.ml_model_id,
        input_reference=obj_in.input_reference,
        status=obj_in.status,
        celery_task_id=obj_in.celery_task_id,
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
    await db.refresh(db_obj, attribute_names=["ml_model"])
    if db_obj.ml_model:
        await db.refresh(db_obj.ml_model, attribute_names=["dataset"])
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


async def get_inference_jobs_by_repository(
    db: AsyncSession, *, repository_id: int, skip: int = 0, limit: int = 100
) -> Tuple[Sequence[InferenceJob], int]:
    """Get inference jobs for a repository with pagination and total count."""
    dataset_ids_stmt = select(Dataset.id).where(Dataset.repository_id == repository_id)
    ml_model_ids_stmt = select(MLModel.id).where(
        MLModel.dataset_id.in_(dataset_ids_stmt)
    )

    stmt_items = (
        select(InferenceJob)
        .options(
            selectinload(InferenceJob.ml_model).selectinload(MLModel.dataset)
        )
        .where(InferenceJob.ml_model_id.in_(ml_model_ids_stmt))
        .order_by(InferenceJob.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result_items = await db.execute(stmt_items)
    items = result_items.scalars().all()

    stmt_total = select(func.count(InferenceJob.id)).where(
        InferenceJob.ml_model_id.in_(ml_model_ids_stmt)
    )
    result_total = await db.execute(stmt_total)
    total = result_total.scalar_one_or_none() or 0

    return items, total


async def get_all_for_commit(
    db: AsyncSession, repo_id: int, commit_hash: str
) -> List[InferenceJob]:
    """
    Retrieves all inference jobs associated with a specific commit hash.
    It checks the input_reference JSON field.
    """
    stmt = (
        select(InferenceJob)
        .options(
            selectinload(InferenceJob.ml_model)
            .selectinload(MLModel.dataset)
            .selectinload(Dataset.repository)
        )
        .filter(
            InferenceJob.input_reference["repo_id"].as_integer() == repo_id,
            InferenceJob.input_reference.op("->>")("commit_hash") == commit_hash,
        )
        .order_by(InferenceJob.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()