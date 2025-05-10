# shared/repositories/hp_search_job_repository.py
import logging
from typing import Optional, Callable, Sequence
from sqlalchemy.orm import Session
from sqlalchemy import select # Import select

from .base_repository import BaseRepository
from shared.db.models import HyperparameterSearchJob, JobStatusEnum # Correct model and enum
from shared.core.config import settings

logger = logging.getLogger(__name__)

class HPSearchJobRepository(BaseRepository[HyperparameterSearchJob]):
    def __init__(self, session_factory: Callable[[], Session]):
        super().__init__(session_factory)
        logger.debug("HPSearchJobRepository initialized.")

    def get_by_id(self, job_id: int) -> Optional[HyperparameterSearchJob]:
        logger.debug(f"HPSearchJobRepo: Fetching job ID {job_id}")
        with self._session_scope() as session:
            # from sqlalchemy.orm import selectinload
            # return session.query(HyperparameterSearchJob).options(selectinload(HyperparameterSearchJob.best_ml_model)).get(job_id)
            return session.get(HyperparameterSearchJob, job_id)

    def get_by_task_id(self, celery_task_id: str) -> Optional[HyperparameterSearchJob]:
        logger.debug(f"HPSearchJobRepo: Fetching job by task ID {celery_task_id}")
        with self._session_scope() as session:
            stmt = select(HyperparameterSearchJob).where(HyperparameterSearchJob.celery_task_id == celery_task_id).limit(1)
            return session.execute(stmt).scalar_one_or_none()

    # Add list_jobs if needed
    def list_jobs(
        self,
        skip: int = 0,
        limit: int = 100,
        dataset_id: Optional[int] = None,
        status: Optional[JobStatusEnum] = None,
        study_name: Optional[str] = None
    ) -> Sequence[HyperparameterSearchJob]:
        logger.debug(f"HPSearchJobRepo: Listing jobs (dataset_id={dataset_id}, status={status}, study={study_name})")
        with self._session_scope() as session:
            from sqlalchemy.orm import selectinload
            stmt = (select(HyperparameterSearchJob)
                    .options(selectinload(HyperparameterSearchJob.best_ml_model))
                    .order_by(HyperparameterSearchJob.created_at.desc()))
            if dataset_id is not None: stmt = stmt.filter(HyperparameterSearchJob.dataset_id == dataset_id)
            if status: stmt = stmt.filter(HyperparameterSearchJob.status == status)
            if study_name: stmt = stmt.filter(HyperparameterSearchJob.optuna_study_name == study_name)
            stmt = stmt.offset(skip).limit(limit)
            return session.execute(stmt).scalars().all()