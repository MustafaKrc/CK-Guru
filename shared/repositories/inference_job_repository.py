# shared/repositories/inference_job_repository.py
import logging
from typing import Optional, Sequence, Dict, Any, Callable # Added Callable
from sqlalchemy.orm import Session # Keep Session for type hint
from sqlalchemy import select, update # Import update
from datetime import datetime, timezone # For updated_at

# Import Base Repository
from .base_repository import BaseRepository
# Import DB Model and Enums/Schemas
from shared.db.models import InferenceJob
from shared.schemas.enums import JobStatusEnum
from shared.schemas.inference_job import InferenceJobCreateInternal, InferenceJobUpdate # Use internal create

logger = logging.getLogger(__name__)

# Inherit from BaseRepository and specify ModelType
class InferenceJobRepository(BaseRepository[InferenceJob]):
    """Handles database operations for InferenceJob."""

    # Add __init__ to accept session_factory
    def __init__(self, session_factory: Callable[[], Session]):
        super().__init__(session_factory) # Initialize BaseRepository
        logger.debug("InferenceJobRepository initialized.")

    def get_by_id(self, job_id: int) -> Optional[InferenceJob]:
        """Gets a single inference job by ID."""
        logger.debug(f"InferenceJobRepo: Fetching job ID {job_id}")
        with self._session_scope() as session:
            # Use session.get for primary key lookup, optionally load relationships
            # from sqlalchemy.orm import selectinload
            # return session.query(InferenceJob).options(selectinload(InferenceJob.ml_model)).get(job_id)
            return session.get(InferenceJob, job_id)


    def get_by_task_id(self, celery_task_id: str) -> Optional[InferenceJob]:
        """Gets an inference job by its Celery task ID (returns first match)."""
        logger.debug(f"InferenceJobRepo: Fetching job by task ID {celery_task_id}")
        with self._session_scope() as session:
            stmt = select(InferenceJob).where(InferenceJob.celery_task_id == celery_task_id).limit(1)
            return session.execute(stmt).scalar_one_or_none()

    def list_jobs(
        self,
        skip: int = 0,
        limit: int = 100,
        model_id: Optional[int] = None,
        status: Optional[JobStatusEnum] = None
    ) -> Sequence[InferenceJob]:
        """Gets multiple inference jobs with optional filtering and pagination."""
        logger.debug(f"InferenceJobRepo: Listing jobs (model_id={model_id}, status={status})")
        with self._session_scope() as session:
            stmt = select(InferenceJob).order_by(InferenceJob.created_at.desc())
            if model_id is not None:
                stmt = stmt.filter(InferenceJob.ml_model_id == model_id)
            if status:
                stmt = stmt.filter(InferenceJob.status == status)
            stmt = stmt.offset(skip).limit(limit)
            return session.execute(stmt).scalars().all()

    def create_job(self, obj_in: InferenceJobCreateInternal) -> InferenceJob:
        """Creates a new inference job record."""
        logger.info(f"InferenceJobRepo: Creating job for model {obj_in.ml_model_id}")
        with self._session_scope() as session:
            # obj_in is already InferenceJobCreateInternal Pydantic model
            db_obj = InferenceJob(**obj_in.model_dump())
            session.add(db_obj)
            session.commit() # Commit to get ID and save
            session.refresh(db_obj)
            logger.info(f"InferenceJobRepo: Created Inference Job ID {db_obj.id}")
        return db_obj

    def update_job(
        self,
        job_id: int,
        obj_in: InferenceJobUpdate # Pydantic model for updates
    ) -> Optional[InferenceJob]:
        """Updates an existing inference job record."""
        logger.info(f"InferenceJobRepo: Updating job ID {job_id}")
        with self._session_scope() as session:
            db_obj = session.get(InferenceJob, job_id)
            if not db_obj:
                logger.error(f"InferenceJobRepo: Job ID {job_id} not found for update.")
                return None

            update_data = obj_in.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)
                else:
                    logger.warning(f"Field '{field}' not found on InferenceJob model for update.")

            # Manually set updated_at if not handled by DB's onupdate
            db_obj.updated_at = datetime.now(timezone.utc)
            session.add(db_obj)
            session.commit()
            session.refresh(db_obj)
            logger.info(f"InferenceJobRepo: Updated Inference Job ID {job_id}, Status: {db_obj.status.value if db_obj.status else 'N/A'}")
        return db_obj

    def delete_job(self, job_id: int) -> bool:
        """Deletes an inference job record. Returns True if deleted."""
        logger.info(f"InferenceJobRepo: Deleting job ID {job_id}")
        with self._session_scope() as session:
            db_obj = session.get(InferenceJob, job_id)
            if db_obj:
                session.delete(db_obj)
                session.commit()
                logger.info(f"InferenceJobRepo: Deleted Inference Job ID {job_id}")
                return True
            logger.warning(f"InferenceJobRepo: Job ID {job_id} not found for deletion.")
            return False