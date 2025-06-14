# worker/ingestion/app/tasks.py
import asyncio  # For async tasks
import logging  # Use standard logging
from pathlib import Path

from celery import shared_task
from celery.exceptions import Reject, Terminated
from services.dependencies import DependencyProvider, StepRegistry
from services.pipeline import PipelineRunner

# --- Import Pipeline Structures ---
from services.steps.base import IngestionContext  # Keep context
from services.strategies import (
    FullHistoryIngestionStrategy,
    SingleCommitFeatureExtractionStrategy,
)

from shared.celery_config.base_task import EventPublishingTask  # Import new base task
from shared.core.config import settings
from shared.db.models import InferenceJob
from shared.db_session import SyncSessionLocal
from shared.schemas.enums import JobStatusEnum

from .main import celery_app

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


async def _ingest_features_for_inference_async(
    self: EventPublishingTask,
    inference_job_id: int,
    repo_id: int,
    commit_hash_input: str,
):
    """
    Celery task to orchestrate feature extraction for a single commit inference
    using the PipelineRunner and SingleCommitFeatureExtractionStrategy.
    """
    task_id = self.request.id
    logger.info(
        f"Task {task_id}: INIT Feature Extraction for InferenceJob {inference_job_id} (Repo: {repo_id}, Commit: {commit_hash_input[:7]})"
    )

    # --- Context Setup ---
    await self.update_task_state(
        state=JobStatusEnum.RUNNING.value,
        status_message="Initializing Feature Extraction Pipeline",
        progress=5,
        job_type="feature_extraction",
        entity_id=inference_job_id,
        entity_type="InferenceJob",
    )

    base_storage_path = Path(settings.STORAGE_BASE_PATH)
    repo_local_path = base_storage_path / "clones" / f"repo_{repo_id}"
    context = IngestionContext(
        repository_id=repo_id,
        repo_local_path=repo_local_path,
        task_instance=self,
        is_single_commit_mode=True,
        target_commit_hash=commit_hash_input,
        inference_job_id=inference_job_id,
        event_job_type="feature_extraction",
        event_entity_id=inference_job_id,
        event_entity_type="InferenceJob",
    )

    # --- Strategy and Dependency Setup ---
    strategy = SingleCommitFeatureExtractionStrategy()
    dependency_provider = DependencyProvider(session_factory=SyncSessionLocal)
    step_registry = StepRegistry()
    runner = PipelineRunner(strategy, step_registry, dependency_provider)
    job_status_updater = dependency_provider.job_status_updater

    try:
        # --- Update Job Status to RUNNING ---
        if not job_status_updater.update_job_start(
            inference_job_id, InferenceJob, task_id
        ):
            # If initial update fails, reject the task permanently
            raise Reject("Initial DB update to RUNNING failed", requeue=False)

        # --- Execute the Pipeline ---
        logger.info(f"Task {task_id}: === Executing Feature Extraction Pipeline ===")
        context = await runner.run(context)
        logger.info(f"Task {task_id}: === Feature Extraction Pipeline Finished ===")

        await self.update_task_state(
            state=JobStatusEnum.SUCCESS.value,
            status_message="Feature extraction complete, dispatching prediction",
            progress=95,
            job_type="feature_extraction",
            entity_id=inference_job_id,
            entity_type="InferenceJob",
        )

        prediction_task_name = "tasks.inference_predict"  # From ml_worker
        prediction_task_args = [inference_job_id]
        # Celery's send_task is synchronous for dispatching, result is AsyncResult
        prediction_task_dispatch = celery_app.send_task(
            prediction_task_name, args=prediction_task_args, queue="ml_queue"
        )

        if not prediction_task_dispatch or not prediction_task_dispatch.id:
            error_msg = (
                "Feature extraction succeeded, but failed to dispatch prediction task."
            )
            logger.critical(f"Task {task_id}: {error_msg}")
            await self.update_task_state(
                state=JobStatusEnum.FAILED.value,
                status_message=error_msg,
                error_details=error_msg,
            )
            # Update InferenceJob DB record to FAILED as well
            job_status_updater.update_job_completion(
                inference_job_id, InferenceJob, JobStatusEnum.FAILED, error_msg
            )
            return {"status": JobStatusEnum.FAILED.value, "error": error_msg}

        success_message = f"Feature extraction complete. Prediction task dispatched: {prediction_task_dispatch.id}"
        await self.update_task_state(
            state=JobStatusEnum.SUCCESS.value,
            status_message=success_message,
            progress=100,
            result_summary={"prediction_task_id": prediction_task_dispatch.id},
        )
        logger.info(f"Task {task_id}: {success_message}")
        # DB record for InferenceJob will be updated by the ML worker upon prediction completion.
        return {
            "status": JobStatusEnum.SUCCESS.value,
            "prediction_task_id": prediction_task_dispatch.id,
        }

    except Terminated:
        status_message = "Task terminated during feature extraction."
        logger.warning(f"Task {task_id}: Terminated (InferenceJob {inference_job_id})")
        job_status_updater.update_job_completion(
            inference_job_id, InferenceJob, JobStatusEnum.FAILED, status_message
        )
        # EventPublishingTask.on_failure or a custom revoke handler would publish REVOKED/FAILED event for Celery Task
        raise
    except Reject as e:  # Specific Celery exception
        logger.info(
            f"Task {task_id}: Rejecting task for InferenceJob {inference_job_id}: {e.reason}"
        )
        # State should have been set before Reject was raised by update_job_start or pipeline
        raise
    except Exception as e:
        # Catch all other exceptions from the PipelineRunner
        pipeline_failed_step = getattr(runner.step_registry, "name", "Unknown")
        error_msg_detail = f"Feature extraction failed at step [{pipeline_failed_step}]: {type(e).__name__}: {str(e)[:200]}"
        logger.critical(
            f"Task {task_id}: Pipeline Error for job {inference_job_id}. {error_msg_detail}: {e}",
            exc_info=True,
        )

        # Update final job status to FAILED using the service
        job_status_updater.update_job_completion(
            inference_job_id, InferenceJob, JobStatusEnum.FAILED, error_msg_detail
        )
        await self.update_task_state(
            state=JobStatusEnum.FAILED.value,
            status_message=error_msg_detail,
            error_details=str(e),
        )
        raise Reject(f"{error_msg_detail}: {e}", requeue=False) from e


async def _ingest_repository_async(
    self: EventPublishingTask, repository_id: int, git_url: str
):
    """
    Real async implementation (verbatim body of the old task).
    """
    task_id = self.request.id
    logger.info(
        f"Task {task_id}: INIT Full Ingestion for repo ID: {repository_id}, URL: {git_url}"
    )
    # --- Context Setup ---
    await self.update_task_state(
        state=JobStatusEnum.RUNNING.value,
        status_message="Initializing Ingestion Pipeline",
        progress=1,
        job_type="repository_ingestion",
        entity_id=repository_id,
        entity_type="Repository",
    )

    base_storage_path = Path(settings.STORAGE_BASE_PATH)
    repo_local_path = base_storage_path / "clones" / f"repo_{repository_id}"
    try:
        repo_local_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        error_msg = f"Failed to create storage directory: {e}"
        logger.critical(f"Task {task_id}: {error_msg}", exc_info=True)
        await self.update_task_state(
            state=JobStatusEnum.FAILED.value,
            status_message=error_msg,
            error_details=str(e),
        )
        raise Reject(error_msg, requeue=False) from e

    context = IngestionContext(
        repository_id=repository_id,
        git_url=git_url,
        repo_local_path=repo_local_path,
        task_instance=self,
        is_single_commit_mode=False,
        event_job_type="repository_ingestion",
        event_entity_id=repository_id,
        event_entity_type="Repository",
    )

    # --- Strategy and Dependency Setup ---
    strategy = FullHistoryIngestionStrategy()
    # If steps become async and need async DB, SyncSessionLocal needs to become async
    dependency_provider = DependencyProvider(session_factory=SyncSessionLocal)
    step_registry = StepRegistry()
    runner = PipelineRunner(strategy, step_registry, dependency_provider)

    try:
        # --- Execute the Pipeline ---
        logger.info(f"Task {task_id}: === Executing Full Ingestion Pipeline ===")
        final_context = await runner.run(context)
        logger.info(f"Task {task_id}: === Full Ingestion Pipeline Finished ===")

        # --- Finalize Task (Success) ---
        final_status_message = "Completed successfully"
        if final_context.warnings:
            final_status_message = (
                f"Completed with warnings: {'; '.join(final_context.warnings)}"
            )
            logger.warning(
                f"Task {task_id}: Full ingestion completed with warnings: {final_context.warnings}"
            )

        result_payload = {  # This is for Celery result backend, not SSE directly
            "status_message": final_status_message,
            "repository_id": final_context.repository_id,
            "commit_guru_metrics_inserted": final_context.inserted_guru_metrics_count,
            "ck_metrics_inserted": final_context.inserted_ck_metrics_count,
            "warnings": final_context.warnings if final_context.warnings else None,
        }
        await self.update_task_state(
            state=JobStatusEnum.SUCCESS.value,
            status_message=final_status_message,
            progress=100,
            result_summary=result_payload,  # Pass structured summary
        )
        logger.info(f"Task {task_id}: Final State: SUCCESS. {final_status_message}")
        return result_payload  # Return for Celery result backend

    except Terminated:
        failed_step_name = getattr(runner.current_step_instance, "name", "Unknown")
        error_msg = f"Full ingestion task terminated during step: {failed_step_name}."
        logger.warning(f"Task {task_id}: {error_msg}")
        # Publish REVOKED event; Celery handles its internal state.
        # EventPublishingTask does not automatically publish on_failure for Terminated
        await self.update_task_state(
            state="REVOKED",  # Celery's state for terminated
            status_message=error_msg,
            error_details=f"Terminated during step: {failed_step_name}",
        )
        raise
    except Reject as e:  # Specific Celery exception
        logger.info(
            f"Task {task_id}: Rejecting task for repo {repository_id}: {e.reason}"
        )
        # State should have been set by the code path that raised Reject
        raise
    except Exception as e:
        # Catch all other exceptions from the PipelineRunner
        pipeline_failed_step = getattr(runner.current_step_instance, "name", "Unknown")
        error_type = type(e).__name__
        error_msg = f"Full ingestion pipeline failed at step '{pipeline_failed_step}' due to {error_type}"
        logger.critical(
            f"Task {task_id}: Pipeline Error for repo {repository_id}. {error_msg}: {e}",
            exc_info=True,
        )
        await self.update_task_state(
            state=JobStatusEnum.FAILED.value,
            status_message=error_msg,
            error_details=f"{error_type}: {str(e)[:500]}",
        )
        raise Reject(f"{error_msg}: {e}", requeue=False) from e


@shared_task(
    bind=True,
    name="tasks.ingest_features_for_inference",
    acks_late=True,
    base=EventPublishingTask,
)
def ingest_features_for_inference_task(
    self: EventPublishingTask,
    inference_job_id: int,
    repo_id: int,
    commit_hash_input: str,
):
    """
    Synchronous wrapper so the prefork worker gets a *real* return
    value, not a coroutine.  All async work happens inside.
    """
    return asyncio.run(
        _ingest_features_for_inference_async(
            self, inference_job_id, repo_id, commit_hash_input
        )
    )


@shared_task(
    bind=True,
    name="tasks.ingest_repository",
    acks_late=True,
    base=EventPublishingTask,
)
def ingest_repository_task(self: EventPublishingTask, repository_id: int, git_url: str):
    """
    Synchronous wrapper for full-history ingestion.
    """
    return asyncio.run(_ingest_repository_async(self, repository_id, git_url))
