# backend/app/crud/crud_ml_model.py
import logging
from typing import Any, Dict, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models.ml_model import MLModel
from shared.schemas.ml_model import MLModelCreate, MLModelUpdate

logger = logging.getLogger(__name__)
# Configure logging level based on your settings if needed
# logger.setLevel(settings.LOG_LEVEL.upper())


async def get_ml_model(db: AsyncSession, model_id: int) -> Optional[MLModel]:
    """Get a single ML model by ID."""
    result = await db.execute(select(MLModel).filter(MLModel.id == model_id))
    return result.scalars().first()


async def get_ml_models(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    model_name: Optional[str] = None,
    model_type: Optional[str] = None,
) -> Sequence[MLModel]:
    """Get multiple ML models with optional filtering and pagination."""
    stmt = select(MLModel).order_by(MLModel.name, MLModel.version.desc())
    if model_name:
        stmt = stmt.filter(MLModel.name == model_name)
    if model_type:
        stmt = stmt.filter(MLModel.model_type == model_type)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


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
    logger.info(f"Updated ML Model ID {db_obj.id}")
    return db_obj


async def delete_ml_model(db: AsyncSession, *, model_id: int) -> Optional[MLModel]:
    """Delete an ML model record."""
    # Note: This only deletes the DB record. Artifact deletion is separate.
    db_obj = await get_ml_model(db, model_id)
    if db_obj:
        model_name = db_obj.name  # Log info before deletion
        model_version = db_obj.version
        await db.delete(db_obj)
        await db.commit()
        logger.info(
            f"Deleted ML Model ID {model_id} (Name: {model_name}, Version: {model_version})"
        )
        # TODO: Queue artifact deletion task here?
    return db_obj
