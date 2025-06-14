# shared/celery_config/base_task.py
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from celery import Task

from shared.core.config import settings
from shared.schemas.enums import JobStatusEnum  # For status consistency
from shared.utils.redis_utils import get_redis_client, publish_task_event

# from celery.utils.log import get_task_logger # No longer needed if using module logger


# Use a standard module logger
logger = logging.getLogger(__name__)
# Ensure your main logging config sets the level for this logger appropriately
# For example, in your FastAPI app or Celery app setup:
# logging.getLogger("shared.celery_config.base_task").setLevel(settings.LOG_LEVEL.upper())


class EventPublishingTask(Task):
    """
    A Celery base Task class that automatically publishes status updates
    to a Redis Pub/Sub channel.
    """

    abstract = True  # Important: This task should not be registered directly
    # _redis_client = None # Removed class-level client to avoid potential state issues across forks/threads

    # Removed classmethod get_redis to fetch client on each call or pass it.
    # For Celery tasks, especially with async operations within, it's safer to
    # acquire resources like DB connections or Redis clients within the task execution context.

    async def _publish_event(self, event_data: dict):
        """Helper to get client and publish. Ensures client is handled per call."""
        redis_client = None
        try:
            redis_client = await get_redis_client()
            await publish_task_event(
                redis_client,
                settings.REDIS_TASK_EVENTS_CHANNEL,  # Use channel from settings
                event_data,
            )
        except ConnectionError as e:  # Catch connection errors from get_redis_client
            logger.error(
                f"Redis connection error in _publish_event for task {self.request.id}: {e}",
                exc_info=True,
            )
        except Exception as e:
            logger.error(
                f"Failed to publish task event via _publish_event for task {self.request.id}: {e}",
                exc_info=True,
            )
        # Note: Not explicitly closing redis_client here as get_redis_client() uses a pool.
        # If get_redis_client() were creating new connections each time, you'd need:
        # finally:
        #     if redis_client:
        #         await redis_client.aclose() # For redis.asyncio >= 4.2

    async def update_task_state(
        self,
        *,  # Make arguments keyword-only for clarity
        state: str,  # Should ideally be JobStatusEnum or TaskStatusEnum
        meta: dict = None,
        job_type: Optional[
            str
        ] = None,  # Application-specific e.g., "repository_ingestion"
        entity_id: Optional[Any] = None,  # e.g., repository_id, dataset_id
        entity_type: Optional[str] = None,  # e.g., "Repository", "Dataset"
        user_id: Optional[Any] = None,  # If available in task context
        progress: Optional[int] = None,
        status_message: Optional[str] = None,
        error_details: Optional[str] = None,
        result_summary: Optional[Any] = None,
    ):
        """
        Updates the Celery task's state and publishes an event to Redis.

        Args:
            state: The new state of the task (e.g., "RUNNING", "SUCCESS", "PROGRESS").
                   Should align with JobStatusEnum or TaskStatusEnum.
            meta: The dictionary to be stored in Celery's result backend.
                  This method will enhance it with progress and status_message.
            job_type: Application-specific type of the job.
            entity_id: ID of the primary entity this task is operating on.
            entity_type: Type of the primary entity.
            user_id: ID of the user who initiated the task, if applicable.
            progress: Current progress percentage (0-100).
            status_message: User-friendly message describing the current step.
            error_details: Detailed error message if state is FAILURE.
            result_summary: Brief summary of results if state is SUCCESS.
        """
        current_meta = meta.copy() if meta is not None else {}

        if progress is not None:
            current_meta["progress"] = progress
        if status_message is not None:
            current_meta["status_message"] = status_message
        elif (
            "status" not in current_meta and state
        ):  # fallback status_message to state if not provided
            current_meta["status_message"] = state.capitalize()

        # Specific handling for FAILURE and SUCCESS states based on arguments
        if state == JobStatusEnum.FAILED.value and error_details:
            current_meta["error_details"] = error_details
        if state == JobStatusEnum.SUCCESS.value and result_summary:
            current_meta["result_summary"] = result_summary

        # Update Celery's internal state
        # The `state` argument to `self.update_state` should be one of Celery's predefined states
        # or a custom state string. JobStatusEnum values are fine if they match Celery's or are custom.
        celery_state_to_set = state
        if (
            state == JobStatusEnum.RUNNING.value
            and progress is not None
            and progress < 100
        ):
            # Celery uses "PROGRESS" as a specific state for tasks that are running and report progress.
            # However, "RUNNING" is also a valid state. If you use custom states, ensure your result backend
            # and any tools consuming status (like Flower or your frontend) understand them.
            # For simplicity, if progress is given, we can use Celery's "PROGRESS" state,
            # otherwise "RUNNING" is fine. Or always use "RUNNING" and put progress in meta.
            # Let's stick to "RUNNING" for simplicity and have progress purely in meta for now,
            # as our JobStatusEnum doesn't have "PROGRESS".
            pass  # Keep state as "RUNNING"

        self.update_state(state=celery_state_to_set, meta=current_meta)
        logger.debug(
            f"Task {self.request.id} state updated to {celery_state_to_set} with meta: {current_meta}"
        )

        # Prepare and publish the event to Redis Pub/Sub
        event_payload = {
            "task_id": str(self.request.id),  # Ensure task_id is string
            "task_name": str(self.name),
            "status": str(state),  # Ensure status is string (enum value)
            "progress": current_meta.get("progress"),
            "status_message": current_meta.get("status_message"),
            "job_type": job_type,
            "entity_id": entity_id,
            "entity_type": entity_type,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_details": (
                current_meta.get("error_details")
                if state == JobStatusEnum.FAILED.value
                else None
            ),
            "result_summary": (
                current_meta.get("result_summary")
                if state == JobStatusEnum.SUCCESS.value
                else None
            ),
        }

        # Filter out None values from payload to keep it clean, unless explicitly needed
        # event_payload_cleaned = {k: v for k, v in event_payload.items() if v is not None}

        await self._publish_event(event_payload)

    # You can also override on_success, on_failure, on_retry if you want to
    # automatically publish events for these lifecycle methods.
    # For example:
    # async def on_success(self, retval, task_id, args, kwargs):
    #     await self.update_task_state(
    #         state=JobStatusEnum.SUCCESS.value,
    #         meta={'result_summary': retval}, # Or a summary of retval
    #         # You might need to pass job_type, entity_id etc. through task headers
    #         # or retrieve them from DB if retval is, e.g., a job_id.
    #     )
    #     logger.info(f"Task {task_id} succeeded.")

    # async def on_failure(self, exc, task_id, args, kwargs, einfo):
    #     await self.update_task_state(
    #         state=JobStatusEnum.FAILED.value,
    #         meta={'error_details': str(exc), 'traceback': einfo.traceback},
    #         # job_type, entity_id...
    #     )
    #     logger.error(f"Task {task_id} failed: {exc}", exc_info=True)
