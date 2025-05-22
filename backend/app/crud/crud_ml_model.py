# backend/app/crud/crud_ml_model.py
import logging
from typing import Any, Dict, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload  # <--- IMPORT THIS

from shared.db.models.dataset import Dataset
from shared.db.models.ml_model import MLModel
from shared.schemas.ml_model import MLModelCreate, MLModelUpdate

logger = logging.getLogger(__name__)


async def get_ml_model(db: AsyncSession, model_id: int) -> Optional[MLModel]:
    """Get a single ML model by ID."""
    stmt = (
        select(MLModel)
        .options(
            selectinload(MLModel.dataset),
            selectinload(MLModel.training_job),
            selectinload(MLModel.hp_search_job),
        )
        .filter(MLModel.id == model_id)
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_ml_models(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    model_name: Optional[str] = None,
    model_type: Optional[str] = None,
    dataset_id: Optional[int] = None,  # Added dataset_id filter
) -> Tuple[Sequence[MLModel], int]:  # Return tuple
    """Get multiple ML models with optional filtering and pagination."""
    stmt_items = (
        select(MLModel)
        .options(  # Eager load for list view as well, for consistency on model objects
            selectinload(MLModel.dataset),
            selectinload(MLModel.training_job),
            selectinload(MLModel.hp_search_job),
        )
        .order_by(MLModel.name, MLModel.version.desc())
    )

    filters = []
    if model_name:
        filters.append(MLModel.name == model_name)
    if model_type:
        filters.append(MLModel.model_type == model_type)
    if dataset_id is not None:
        filters.append(MLModel.dataset_id == dataset_id)

    if filters:
        stmt_items = stmt_items.where(*filters)

    # Count before applying offset/limit for items
    stmt_total = select(func.count(MLModel.id))
    if filters:
        stmt_total = stmt_total.where(*filters)

    result_total = await db.execute(stmt_total)
    total = result_total.scalar_one_or_none() or 0

    stmt_items = stmt_items.offset(skip).limit(limit)
    result_items = await db.execute(stmt_items)
    items = result_items.scalars().all()

    return items, total


async def get_latest_model_version(db: AsyncSession, model_name: str) -> Optional[int]:
    """Gets the highest version number for a given model name."""
    stmt = select(func.max(MLModel.version)).filter(MLModel.name == model_name)
    result = await db.execute(stmt)
    max_version = result.scalar_one_or_none()
    return max_version


async def create_ml_model(db: AsyncSession, *, obj_in: MLModelCreate) -> MLModel:
    """Create a new ML model record."""
    # Version should be provided in obj_in, determined before calling create
    db_obj = MLModel(**obj_in.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    logger.info(
        f"Created ML Model ID {db_obj.id} (Name: {db_obj.name}, Version: {db_obj.version})"
    )
    return db_obj


async def update_ml_model(
    db: AsyncSession, *, db_obj: MLModel, obj_in: MLModelUpdate | Dict[str, Any]
) -> MLModel:
    """Update an existing ML model record."""
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        # Use Pydantic V2 model_dump method
        update_data = obj_in.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(db_obj, field, value)

    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    await db.refresh(
        db_obj, attribute_names=["dataset", "training_job", "hp_search_job"]
    )
    logger.info(f"Updated ML Model ID {db_obj.id}")
    return db_obj


async def delete_ml_model(db: AsyncSession, *, model_id: int) -> Optional[MLModel]:
    """Delete an ML model record."""
    db_obj = await get_ml_model(db, model_id)
    if db_obj:
        model_name = db_obj.name
        model_version = db_obj.version
        await db.delete(db_obj)
        await db.commit()
        logger.info(
            f"Deleted ML Model ID {model_id} (Name: {model_name}, Version: {model_version})"
        )
    return db_obj


async def get_ml_models_by_repository(
    db: AsyncSession, *, repository_id: int, skip: int = 0, limit: int = 100
) -> Tuple[Sequence[MLModel], int]:
    """Get ML models associated with a specific repository, with total count."""
    dataset_ids_stmt = select(Dataset.id).where(Dataset.repository_id == repository_id)
    stmt_items = (
        select(MLModel)
        .options(
            selectinload(MLModel.dataset),
            selectinload(MLModel.training_job),
            selectinload(MLModel.hp_search_job),
        )
        .where(MLModel.dataset_id.in_(dataset_ids_stmt))
        .order_by(MLModel.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result_items = await db.execute(stmt_items)
    items = result_items.scalars().all()

    stmt_total = select(func.count(MLModel.id)).where(
        MLModel.dataset_id.in_(dataset_ids_stmt)
    )
    result_total = await db.execute(stmt_total)
    total = result_total.scalar_one_or_none() or 0

    return items, total
