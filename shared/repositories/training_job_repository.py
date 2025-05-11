# shared/repositories/training_job_repository.py
import logging
from typing import Callable, Optional, Sequence

from sqlalchemy import select  # Import select
from sqlalchemy.orm import Session

from shared.db.models import JobStatusEnum, TrainingJob  # Correct model and enum

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class TrainingJobRepository(BaseRepository[TrainingJob]):
    def __init__(self, session_factory: Callable[[], Session]):
        super().__init__(session_factory)
        logger.debug("TrainingJobRepository initialized.")

    def get_by_id(self, job_id: int) -> Optional[TrainingJob]:
        logger.debug(f"TrainingJobRepo: Fetching job ID {job_id}")
        with self._session_scope() as session:
            # Optionally load related entities if always needed with the job
            # from sqlalchemy.orm import selectinload
            # return session.query(TrainingJob).options(selectinload(TrainingJob.ml_model)).get(job_id)
            return session.get(TrainingJob, job_id)

    def get_by_task_id(self, celery_task_id: str) -> Optional[TrainingJob]:
        logger.debug(f"TrainingJobRepo: Fetching job by task ID {celery_task_id}")
        with self._session_scope() as session:
            stmt = (
                select(TrainingJob)
                .where(TrainingJob.celery_task_id == celery_task_id)
                .limit(1)
            )
            return session.execute(stmt).scalar_one_or_none()

    # Add list_jobs if needed for ML worker (currently in backend CRUD)
    def list_jobs(
        self,
        skip: int = 0,
        limit: int = 100,
        dataset_id: Optional[int] = None,
        status: Optional[JobStatusEnum] = None,
    ) -> Sequence[TrainingJob]:
        logger.debug(
            f"TrainingJobRepo: Listing jobs (dataset_id={dataset_id}, status={status})"
        )
        with self._session_scope() as session:
            from sqlalchemy.orm import selectinload  # Local import for clarity

            stmt = (
                select(TrainingJob)
                .options(selectinload(TrainingJob.ml_model))
                .order_by(TrainingJob.created_at.desc())
            )
            if dataset_id is not None:
                stmt = stmt.filter(TrainingJob.dataset_id == dataset_id)
            if status:
                stmt = stmt.filter(TrainingJob.status == status)
            stmt = stmt.offset(skip).limit(limit)
            return session.execute(stmt).scalars().all()
