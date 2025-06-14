# backend/app/services/commit_service.py
import logging

from app import crud
from app.core.celery_app import backend_celery_app
from celery import Celery
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db_session import get_async_db_session
from shared.schemas.commit import CommitPageResponse
from shared.schemas.enums import CommitIngestionStatusEnum
from shared.schemas.task import TaskResponse

logger = logging.getLogger(__name__)


class CommitService:
    def __init__(
        self,
        db: AsyncSession = Depends(get_async_db_session),
        celery_app: Celery = Depends(lambda: backend_celery_app),
    ):
        self.db = db
        self.celery_app = celery_app

    async def get_commit_page_data(
        self, repo_id: int, commit_hash: str
    ) -> CommitPageResponse:
        """
        Gets all data needed for the commit page. If data doesn't exist,
        it returns a status indicating it's not ingested.
        """
        commit_detail = await crud.crud_commit_details.get_by_hash(
            self.db, repo_id, commit_hash
        )

        if commit_detail is None:
            return CommitPageResponse(
                ingestion_status=CommitIngestionStatusEnum.NOT_INGESTED
            )

        if commit_detail.ingestion_status != CommitIngestionStatusEnum.COMPLETE:
            return CommitPageResponse(
                ingestion_status=commit_detail.ingestion_status,
                celery_ingestion_task_id=commit_detail.celery_ingestion_task_id,
            )

        # If complete, fetch related inference jobs
        # NOTE: A new CRUD method will be needed for this
        inference_jobs = await crud.crud_inference_job.get_all_for_commit(
            self.db, repo_id, commit_hash
        )

        return CommitPageResponse(
            ingestion_status=CommitIngestionStatusEnum.COMPLETE,
            details=commit_detail,
            inference_jobs=inference_jobs,
        )

    async def trigger_ingestion_for_commit(
        self, repo_id: int, commit_hash: str
    ) -> TaskResponse:
        """
        Triggers the ingestion pipeline for a specific commit.
        """
        existing_detail = await crud.crud_commit_details.get_by_hash(
            self.db, repo_id, commit_hash
        )

        if existing_detail and existing_detail.ingestion_status in [
            CommitIngestionStatusEnum.RUNNING,
            CommitIngestionStatusEnum.COMPLETE,
        ]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Commit is already {existing_detail.ingestion_status.value}. A new ingestion cannot be started.",
            )

        # Create or retrieve the placeholder to get its ID
        if not existing_detail:
            placeholder = await crud.crud_commit_details.create_placeholder(
                self.db, repo_id, commit_hash
            )
            detail_id = placeholder.id
        else:
            detail_id = existing_detail.id

        # Dispatch the task. We pass the commit_details ID so the worker can update it.
        # The first argument `inference_job_id` is now a bit of a misnomer for this task.
        # We can pass `None` as it's not strictly an inference job yet. The worker context can handle this.
        task = self.celery_app.send_task(
            "tasks.ingest_features_for_inference",
            args=[None, repo_id, commit_hash],
            queue="ingestion",
        )

        # Update the placeholder with the new task ID
        await crud.crud_commit_details.set_ingestion_task(self.db, detail_id, task.id)

        return TaskResponse(task_id=task.id)
