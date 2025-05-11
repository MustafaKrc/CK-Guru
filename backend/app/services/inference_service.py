# backend/services/inference_service.py
import logging
from typing import Tuple

from app import crud
from app.core.celery_app import backend_celery_app

# Import TaskStatusService if it exists, otherwise use AsyncResult directly for now
from celery import Celery
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared import schemas
from shared.core.config import settings
from shared.db_session import get_async_db_session
from shared.exceptions import ConflictError, InternalError, NotFoundError
from shared.schemas.enums import JobStatusEnum

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


class InferenceService:
    """
    Facade for managing the inference workflow initiation and status checking.
    """

    def __init__(
        self,
        db: AsyncSession = Depends(get_async_db_session),
        celery_app: Celery = Depends(lambda: backend_celery_app),  # Inject Celery app
    ):
        self.db = db
        self.celery_app = celery_app
        # Consider injecting specific CRUD instances if needed for finer control/testing
        # self.crud_repo = crud.crud_repository
        # self.crud_model = crud.crud_ml_model
        # self.crud_job = crud.crud_inference_job

    async def trigger_inference(
        self, repo_id: int, commit_hash: str, model_id: int, trigger_source: str
    ) -> Tuple[int, str]:
        """
        Validates inputs, creates an InferenceJob record, and dispatches the
        initial feature extraction task.

        Returns:
            Tuple of (inference_job_id, celery_task_id).
        Raises:
            HTTPException: On validation errors or dispatch failures.
        """
        logger.info(
            f"Service: Starting inference trigger process for Repo={repo_id}, Commit={commit_hash[:7]}, Model={model_id}"
        )

        # --- Validation ---
        try:
            repo = await crud.crud_repository.get_repository(self.db, repo_id=repo_id)
            if not repo:
                raise NotFoundError(f"Repository {repo_id} not found.")

            model = await crud.crud_ml_model.get_ml_model(self.db, model_id=model_id)
            if not model:
                raise NotFoundError(f"ML Model {model_id} not found.")
            if not model.s3_artifact_path:
                raise ConflictError(
                    f"ML Model {model_id} is not ready (missing artifact path)."
                )
        except NotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except ConflictError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e
        except Exception as e:
            logger.error(f"Unexpected validation error: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Validation error.",
            ) from e

        # --- Create Job Record ---
        try:
            job_schema = schemas.InferenceJobCreate(
                ml_model_id=model_id,
                input_reference={
                    "commit_hash": commit_hash,
                    "repo_id": repo_id,
                    "trigger_source": trigger_source,
                },
                status=JobStatusEnum.PENDING,  # Start as PENDING
            )
            db_job = await crud.crud_inference_job.create_inference_job(
                db=self.db, obj_in=job_schema
            )
            job_id = db_job.id
            await self.db.flush()  # Ensure ID is available
            logger.info(f"Service: Created InferenceJob ID {job_id}")
        except Exception as e:
            logger.error(
                f"Service: Failed to create InferenceJob record: {e}", exc_info=True
            )
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create job record.",
            ) from e

        # --- Dispatch Feature Extraction Task ---
        task_name = "tasks.ingest_features_for_inference"  # Task in ingestion worker
        args = [job_id, repo_id, commit_hash]
        task_id = None
        try:
            task = self.celery_app.send_task(task_name, args=args, queue="ingestion")
            if not task or not task.id:
                raise InternalError("Celery dispatch returned invalid task object.")
            task_id = task.id
            logger.info(
                f"Service: Dispatched feature extraction task {task_id} for job {job_id}"
            )
        except Exception as e:
            logger.error(
                f"Service: Failed to dispatch Celery task '{task_name}': {e}",
                exc_info=True,
            )
            # Attempt to mark job as failed immediately
            try:
                fail_update = schemas.InferenceJobUpdate(
                    status=JobStatusEnum.FAILED,
                    status_message=f"Feature extraction task dispatch failed: {e}",
                )
                await crud.crud_inference_job.update_inference_job(
                    db=self.db, db_obj=db_job, obj_in=fail_update
                )
                await self.db.commit()
            except Exception as db_fail_err:
                logger.error(
                    f"Failed to mark job {job_id} as failed after dispatch error: {db_fail_err}"
                )
                await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to dispatch background task.",
            ) from e

        # --- Update Job with Task ID ---
        try:
            update_schema = schemas.InferenceJobUpdate(celery_task_id=task_id)
            await crud.crud_inference_job.update_inference_job(
                db=self.db, db_obj=db_job, obj_in=update_schema
            )
            await self.db.commit()
            logger.info(f"Service: Updated job {job_id} with task {task_id}")
        except Exception as e:
            logger.error(
                f"Service: Failed to update job {job_id} with task ID {task_id}: {e}",
                exc_info=True,
            )
            await self.db.rollback()
            # Difficult state: task dispatched but DB record doesn't reflect it.
            # Consider queuing a cleanup task or raising an alert.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to link task ID to job.",
            ) from e

        return job_id, task_id

    async def get_inference_status(self, job_id: int) -> schemas.InferenceJobRead:
        """Gets the combined status (DB + Celery) for an inference job."""
        logger.debug(f"Service: Getting status for InferenceJob {job_id}")
        db_job = await crud.crud_inference_job.get_inference_job(self.db, job_id=job_id)
        if not db_job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inference Job {job_id} not found.",
            )

        # Convert DB record to Pydantic schema first
        response_data = schemas.InferenceJobRead.model_validate(db_job)

        # TODO: Fetch and potentially merge Celery task status if needed for more real-time info?
        # For now, relying on the DB status updated by workers.
        # if db_job.celery_task_id:
        #     task_status_info = task_status_service.get_status(db_job.celery_task_id)
        #     # Merge task_status_info into response_data if desired

        return response_data
