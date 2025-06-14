# shared/repositories/dataset_repository.py
import logging
from typing import Any, Dict, Optional, Sequence

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from shared.db.models import Dataset  # Import Repository if needed for relations
from shared.schemas.dataset import DatasetCreate, DatasetUpdate
from shared.schemas.enums import DatasetStatusEnum

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class DatasetRepository(BaseRepository[Dataset]):
    """Handles synchronous database operations for Dataset."""

    def get_record(self, dataset_id: int) -> Optional[Dataset]:
        """Gets a full Dataset record by ID."""
        logger.debug(f"DatasetRepo: Fetching record for ID {dataset_id}")
        with self._session_scope() as session:
            return session.get(Dataset, dataset_id)

    def get_storage_path(self, dataset_id: int) -> Optional[str]:
        """Gets only the storage_path for a Dataset by ID."""
        logger.debug(f"DatasetRepo: Fetching storage path for ID {dataset_id}")
        with self._session_scope() as session:
            stmt = select(Dataset.storage_path).where(Dataset.id == dataset_id)
            path = session.execute(stmt).scalar_one_or_none()
        return path

    def get_by_repository(
        self, repository_id: int, skip: int = 0, limit: int = 100
    ) -> Sequence[Dataset]:
        """Get datasets associated with a specific repository."""
        with self._session_scope() as session:
            stmt = (
                select(Dataset)
                .filter(Dataset.repository_id == repository_id)
                .order_by(Dataset.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            return session.execute(stmt).scalars().all()

    def create(self, obj_in: DatasetCreate, repository_id: int) -> Dataset:
        """Create a new dataset definition."""
        with self._session_scope() as session:
            try:
                # Pydantic v2: model_dump() instead of dict()
                create_data = obj_in.model_dump()
                db_obj = Dataset(
                    **create_data,
                    repository_id=repository_id,
                    status=DatasetStatusEnum.PENDING,
                )
                session.add(db_obj)
                session.commit()
                session.refresh(db_obj)
                logger.info(
                    f"Created dataset definition ID {db_obj.id} for repository {repository_id}"
                )
                return db_obj
            except SQLAlchemyError as e:
                logger.error(
                    f"DatasetRepository: DB error creating dataset for repo {repository_id}: {e}",
                    exc_info=True,
                )
                raise
            except Exception as e:
                logger.error(
                    f"DatasetRepository: Unexpected error creating dataset for repo {repository_id}: {e}",
                    exc_info=True,
                )
                raise

    def update(self, db_obj: Dataset, obj_in: DatasetUpdate) -> Dataset:
        """Update an existing dataset definition (e.g., name, description, config)."""
        with self._session_scope() as session:
            try:
                # Check if object is detached and merge if necessary
                if db_obj not in session:
                    db_obj = session.merge(db_obj)

                # Pydantic v2: model_dump() with exclude_unset
                update_data = obj_in.model_dump(exclude_unset=True)
                for field, value in update_data.items():
                    if hasattr(db_obj, field):
                        setattr(db_obj, field, value)
                # Manually update 'updated_at' for sync sessions if model doesn't handle it
                if hasattr(db_obj, "updated_at"):
                    from datetime import datetime, timezone

                    db_obj.updated_at = datetime.now(timezone.utc)

                session.add(
                    db_obj
                )  # Add the modified object (important after merge/update)
                session.commit()
                session.refresh(db_obj)
                logger.info(f"Updated dataset ID {db_obj.id}")
                return db_obj
            except SQLAlchemyError as e:
                logger.error(
                    f"DatasetRepository: DB error updating dataset {db_obj.id}: {e}",
                    exc_info=True,
                )
                raise
            except Exception as e:
                logger.error(
                    f"DatasetRepository: Unexpected error updating dataset {db_obj.id}: {e}",
                    exc_info=True,
                )
                raise

    def update_status(
        self,
        dataset_id: int,
        status: DatasetStatusEnum,
        status_message: Optional[str] = None,
        storage_path: Optional[str] = None,
        background_data_path: Optional[str] = None,
        celery_task_id: Optional[str] = None,
    ) -> Optional[Dataset]:
        """Update the status, message, paths, and task ID of a dataset."""
        values_to_update: Dict[str, Any] = {"status": status}
        if status_message is not None:
            values_to_update["status_message"] = status_message[
                :1000
            ]  # Truncate message
        if storage_path is not None:
            values_to_update["storage_path"] = storage_path
        if background_data_path is not None:
            values_to_update["background_data_path"] = background_data_path
        if celery_task_id is not None:
            values_to_update["celery_task_id"] = celery_task_id

        # Add updated_at timestamp manually
        from datetime import datetime, timezone

        values_to_update["updated_at"] = datetime.now(timezone.utc)

        with self._session_scope() as session:
            try:
                stmt = (
                    update(Dataset)
                    .where(Dataset.id == dataset_id)
                    .values(**values_to_update)
                    # execution_options(synchronize_session=False) might be needed if relationships are complex
                )
                result = session.execute(stmt)
                session.commit()

                if result.rowcount == 0:
                    logger.warning(
                        f"Attempted to update status for non-existent dataset ID {dataset_id}"
                    )
                    return None
                else:
                    logger.info(
                        f"Updated status for dataset ID {dataset_id} to {status.value}"
                    )
                    # Fetch the updated object after commit
                    return session.get(Dataset, dataset_id)
            except SQLAlchemyError as e:
                logger.error(
                    f"DatasetRepository: DB error updating status for dataset {dataset_id}: {e}",
                    exc_info=True,
                )
                raise
            except Exception as e:
                logger.error(
                    f"DatasetRepository: Unexpected error updating status for dataset {dataset_id}: {e}",
                    exc_info=True,
                )
                raise

    def delete(self, dataset_id: int) -> bool:
        """Delete a dataset definition by ID. Returns True if deleted, False otherwise."""
        with self._session_scope() as session:
            try:
                db_obj = session.get(Dataset, dataset_id)
                if db_obj:
                    repo_id = db_obj.repository_id
                    session.delete(db_obj)
                    session.commit()
                    logger.info(
                        f"Deleted dataset definition ID {dataset_id} for repository {repo_id}"
                    )
                    return True
                else:
                    logger.warning(
                        f"Dataset definition ID {dataset_id} not found for deletion."
                    )
                    return False
            except SQLAlchemyError as e:
                logger.error(
                    f"DatasetRepository: DB error deleting dataset {dataset_id}: {e}",
                    exc_info=True,
                )
                raise
            except Exception as e:
                logger.error(
                    f"DatasetRepository: Unexpected error deleting dataset {dataset_id}: {e}",
                    exc_info=True,
                )
                raise

    def get_by_id(self, dataset_id: int) -> Optional[Dataset]:
        """Get a dataset by ID."""
        with self._session_scope() as session:
            return session.get(Dataset, dataset_id)

    def update_config(self, dataset_id: int, new_config: Dict[str, Any]) -> bool:
        """Updates the config JSON for a specific dataset."""
        with self._session_scope() as session:
            try:
                stmt = (
                    update(Dataset)
                    .where(Dataset.id == dataset_id)
                    .values(config=new_config)
                )
                result = session.execute(stmt)
                session.commit()
                if result.rowcount == 0:
                    logger.warning(
                        f"Attempted to update config for non-existent dataset ID {dataset_id}"
                    )
                    return False
                logger.info(f"Successfully updated config for dataset ID {dataset_id}")
                return True
            except SQLAlchemyError as e:
                logger.error(
                    f"DB error updating config for dataset {dataset_id}: {e}",
                    exc_info=True,
                )
                session.rollback()
                raise
