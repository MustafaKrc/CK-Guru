# backend/app/services/inference_orchestrator.py
import logging
from typing import Tuple

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.schemas import InferenceJobCreate # Use alias from __init__
from shared.schemas.enums import JobStatusEnum
from shared.core.config import settings # To access celery app instance name/queue if needed
from app.core.celery_app import backend_celery_app
from app import crud # Import backend crud module

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

class InferenceOrchestrator:
    """Handles the initiation of the inference pipeline."""

    async def trigger_inference_pipeline(
        self,
        db: AsyncSession,
        repo_id: int,
        commit_hash: str,
        ml_model_id: int,
        trigger_source: str
    ) -> Tuple[int, str]:
        """
        Creates an InferenceJob record and dispatches the initial feature extraction task.

        Args:
            db: The database session.
            repo_id: ID of the repository.
            commit_hash: Target commit hash for inference.
            ml_model_id: ID of the ML model to use.
            trigger_source: String indicating the source ('manual' or 'webhook').

        Returns:
            A tuple containing (inference_job_id, initial_task_id).

        Raises:
            HTTPException: If validation fails or task dispatch fails.
        """
        logger.info(f"Triggering inference pipeline for repo {repo_id}, commit {commit_hash[:7]}, model {ml_model_id} (Source: {trigger_source})")

        # --- Validate Inputs ---
        # 1. Check Repository
        repo = await crud.crud_repository.get_repository(db, repo_id=repo_id)
        if not repo:
            logger.error(f"Repository ID {repo_id} not found.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository {repo_id} not found.")

        # 2. Check ML Model
        model = await crud.crud_ml_model.get_ml_model(db, model_id=ml_model_id)
        if not model:
            logger.error(f"ML Model ID {ml_model_id} not found.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ML Model {ml_model_id} not found.")
        if not model.s3_artifact_path:
             logger.error(f"ML Model ID {ml_model_id} exists but has no artifact path.")
             raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"ML Model {ml_model_id} has no artifact path.")

        # --- Create InferenceJob Record ---
        try:
            inference_job_data = InferenceJobCreate(
                ml_model_id=ml_model_id,
                input_reference={
                    "commit_hash": commit_hash,
                    "repo_id": repo_id, # Include repo_id for clarity
                    "trigger_source": trigger_source
                },
                status=JobStatusEnum.PENDING,
                celery_task_id=None # Will be set after dispatch
            )
            # Use the specific CRUD function for inference jobs
            db_inference_job = await crud.crud_inference_job.create_inference_job(db=db, obj_in=inference_job_data)
            inference_job_id = db_inference_job.id
            logger.info(f"Created InferenceJob record ID: {inference_job_id}")
        except Exception as e:
            logger.error(f"Failed to create InferenceJob record in DB: {e}", exc_info=True)
            # Don't raise HTTPException directly, let caller handle
            raise RuntimeError(f"Failed to create InferenceJob record: {e}") from e

        # --- Dispatch Celery Task ---
        task_name = "tasks.ingest_specific_commit" # Ensure this matches the worker task name
        ingestion_queue = "ingestion" # Queue for the ingestion worker

        try:
            task = backend_celery_app.send_task(
                task_name,
                args=[repo_id, commit_hash, inference_job_id], # Pass necessary IDs
                queue=ingestion_queue
            )
            initial_task_id = task.id
            logger.info(f"Dispatched task '{task_name}' to queue '{ingestion_queue}' for InferenceJob {inference_job_id}, Task ID: {initial_task_id}")

            # --- Update Job with Task ID ---
            # Use the specific update function for inference jobs
            update_data = crud.crud_inference_job.InferenceJobUpdate(celery_task_id=initial_task_id)
            await crud.crud_inference_job.update_inference_job(db=db, db_obj=db_inference_job, obj_in=update_data)
            await db.commit() # Commit the task ID update
            logger.info(f"Updated InferenceJob {inference_job_id} with initial task ID {initial_task_id}")

            return inference_job_id, initial_task_id

        except Exception as e:
            logger.error(f"Failed to dispatch Celery task '{task_name}' or update job for InferenceJob {inference_job_id}: {e}", exc_info=True)
            # Attempt to mark the job as FAILED
            try:
                fail_update = crud.crud_inference_job.InferenceJobUpdate(
                    status=JobStatusEnum.FAILED,
                    status_message=f"Failed to queue feature extraction task: {e}"
                )
                # Refetch might be needed if session state is uncertain
                db_job_fail = await crud.crud_inference_job.get_inference_job(db, inference_job_id)
                if db_job_fail:
                    await crud.crud_inference_job.update_inference_job(db=db, db_obj=db_job_fail, obj_in=fail_update)
                    await db.commit()
            except Exception as update_err:
                logger.error(f"Failed to mark InferenceJob {inference_job_id} as failed after task dispatch error: {update_err}")
                await db.rollback() # Rollback if marking as failed also failed

            # Raise HTTPException to signal failure to the API endpoint
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initiate inference pipeline task.",
            ) from e
