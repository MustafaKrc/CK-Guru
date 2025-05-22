# backend/app/crud/crud_dataset.py
import logging
from typing import Any, Dict, Optional, Sequence, Tuple

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.core.config import settings
from shared.db.models.dataset import Dataset, DatasetStatusEnum
from shared.schemas.dataset import DatasetCreate, DatasetUpdate
from shared.schemas.enums import (
    DatasetStatusEnum as DatasetStatusEnumSchema,
)  # For filtering

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


# --- Get Datasets ---
async def get_dataset(db: AsyncSession, dataset_id: int) -> Optional[Dataset]:
    """Get a single dataset by ID."""
    result = await db.execute(
        select(Dataset)
        .options(
            selectinload(Dataset.repository)
        )  # Eager load repository if often needed
        .filter(Dataset.id == dataset_id)
    )
    return result.scalars().first()


async def get_all_datasets(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    status: Optional[DatasetStatusEnumSchema] = None,
    # Add other filters like user_id when auth is integrated
) -> Tuple[Sequence[Dataset], int]:
    """Get all datasets with pagination and optional filtering."""
    stmt_items = (
        select(Dataset)
        .options(selectinload(Dataset.repository))  # Good to load repository name
        .order_by(Dataset.created_at.desc())
    )

    filters = []
    if status:
        filters.append(Dataset.status == status)
    # Example: if user_id filtering is added
    # if user_id:
    #     filters.append(Dataset.owner_id == user_id) # Assuming an owner_id field

    if filters:
        stmt_items = stmt_items.where(*filters)

    stmt_total = select(func.count(Dataset.id))
    if filters:
        stmt_total = stmt_total.where(*filters)

    result_total = await db.execute(stmt_total)
    total = result_total.scalar_one_or_none() or 0

    stmt_items = stmt_items.offset(skip).limit(limit)
    result_items = await db.execute(stmt_items)
    items = result_items.scalars().all()

    return items, total


async def get_datasets_by_repository(
    db: AsyncSession, *, repository_id: int, skip: int = 0, limit: int = 100
) -> Tuple[Sequence[Dataset], int]:
    """Get datasets associated with a specific repository, with total count."""

    # Query for items
    stmt_items = (
        select(Dataset)
        .filter(Dataset.repository_id == repository_id)
        .order_by(Dataset.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result_items = await db.execute(stmt_items)
    items = result_items.scalars().all()

    # Query for total count
    stmt_total = select(func.count(Dataset.id)).filter(
        Dataset.repository_id == repository_id
    )
    result_total = await db.execute(stmt_total)
    total = result_total.scalar_one_or_none() or 0

    return items, total


# --- Create Dataset ---
async def create_dataset(
    db: AsyncSession, *, obj_in: DatasetCreate, repository_id: int
) -> Dataset:
    """Create a new dataset definition."""
    # Create dictionary from Pydantic model, ensuring config is properly structured
    create_data = obj_in.model_dump()
    db_obj = Dataset(
        **create_data, repository_id=repository_id, status=DatasetStatusEnum.PENDING
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    logger.info(
        f"Created dataset definition ID {db_obj.id} for repository {repository_id}"
    )
    return db_obj


# --- Update Dataset (Example - if needed for config changes, etc.) ---
async def update_dataset(
    db: AsyncSession,
    *,
    db_obj: Dataset,  # Existing dataset object
    obj_in: DatasetUpdate,  # Schema for updates (define this if needed)
) -> Dataset:
    """Update an existing dataset definition (e.g., name, description, config)."""
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    logger.info(f"Updated dataset ID {db_obj.id}")
    return db_obj


# --- Update Dataset Status (Used by Worker or API after task completion/failure) ---
async def update_dataset_status(
    db: AsyncSession,
    *,
    dataset_id: int,
    status: DatasetStatusEnum,
    status_message: Optional[str] = None,
    storage_path: Optional[str] = None,
) -> Optional[Dataset]:
    """Update the status, message, and storage path of a dataset."""
    values_to_update: Dict[str, Any] = {"status": status}
    if status_message is not None:
        values_to_update["status_message"] = status_message
    if storage_path is not None:
        values_to_update["storage_path"] = storage_path
    if not values_to_update:
        return await get_dataset(db, dataset_id)  # Nothing to update

    stmt = (
        update(Dataset)
        .where(Dataset.id == dataset_id)
        .values(**values_to_update)
        .returning(Dataset)  # Return the updated object
    )
    result = await db.execute(stmt)
    await db.commit()  # Commit the change
    updated_dataset = result.scalar_one_or_none()

    if updated_dataset:
        logger.info(f"Updated status for dataset ID {dataset_id} to {status.value}")
    else:
        logger.warning(
            f"Attempted to update status for non-existent dataset ID {dataset_id}"
        )

    # Optionally refresh relationships if needed after update
    # if updated_dataset: await db.refresh(updated_dataset, attribute_names=['repository'])

    return updated_dataset


# --- Delete Dataset ---
async def delete_dataset(db: AsyncSession, *, dataset_id: int) -> Optional[Dataset]:
    """Delete a dataset definition by ID."""
    db_obj = await get_dataset(db, dataset_id)
    if db_obj:
        repo_id = db_obj.repository_id
        # Note: Deleting the DB record doesn't delete the generated file.
        # File deletion logic should be handled separately, perhaps triggered here.
        await db.delete(db_obj)
        await db.commit()
        logger.info(
            f"Deleted dataset definition ID {dataset_id} for repository {repo_id}"
        )
        # TODO: Add logic here or in a background task to delete the actual dataset file
        # from storage_path if it exists.
    return db_obj
