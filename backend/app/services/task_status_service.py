# backend/app/services/task_status_service.py
import logging
from typing import Any, Optional, Dict

from celery import Celery
from celery.result import AsyncResult

from shared import schemas # Import your response schema
from shared.schemas.task import TaskStatusResponse, TaskStatusEnum # Ensure enum is accessible
from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

class TaskStatusService:
    """
    Service class to retrieve and interpret Celery task status information reliably.
    Acts as an Adapter over Celery's AsyncResult.
    """
    def __init__(self, celery_app_instance: Celery):
        if celery_app_instance is None:
            raise ValueError("Celery app instance is required for TaskStatusService.")
        self.celery_app = celery_app_instance
        logger.debug("TaskStatusService initialized.")

    def get_status(self, task_id: str) -> schemas.TaskStatusResponse:
        """
        Retrieves the status of a Celery task, handling potential errors
        in accessing result backend data.

        Args:
            task_id: The ID of the Celery task.

        Returns:
            A TaskStatusResponse object.
        """
        logger.debug(f"Getting status for task ID: {task_id}")
        async_result = AsyncResult(task_id, app=self.celery_app)
        task_state_str = async_result.state

        # Initialize response fields
        final_result: Any | None = None
        error_details: str | None = None
        progress: Optional[int] = None
        status_message: Optional[str] = None

        try:
            # --- Process based on Celery State ---
            if task_state_str == TaskStatusEnum.PENDING.value:
                pass # Defaults are okay

            elif task_state_str == TaskStatusEnum.SUCCESS.value:
                try:
                    final_result = async_result.result
                    # Safely extract progress/status from result if it's a dict
                    if isinstance(final_result, dict):
                        status_message = final_result.get('status', status_message)
                        # Optionally set progress based on result
                        progress = final_result.get('progress', progress)
                        if progress is None and status_message: # Set 100 if success message exists but no progress
                            progress = 100
                    elif final_result is not None:
                        # If result is not None and not dict, set progress to 100
                        progress = 100
                except Exception as e:
                    logger.warning(f"Error accessing result for SUCCESS task {task_id}: {e}", exc_info=True)
                    # Optionally indicate result retrieval failure
                    # final_result = {"error": "Failed to retrieve result"}

            elif task_state_str == TaskStatusEnum.FAILURE.value:
                try:
                    task_info = async_result.info
                    task_result_on_fail = async_result.result # Check result field too

                    # Attempt to extract meaningful error details
                    if isinstance(task_info, Exception):
                        error_details = f"Exception: {str(task_info)}"
                    elif isinstance(task_info, dict):
                        # Safely get type and message
                        exc_type = task_info.get('exc_type', 'UnknownType')
                        exc_message_raw = task_info.get('exc_message', ['No message']) # Default to list for repr
                        # Use repr for message as it might be complex (e.g., tuple)
                        exc_message = repr(exc_message_raw)
                        error_details = f"Type: {exc_type}, Message: {exc_message}"
                        # Try to get progress/status metadata potentially stored before failure
                        progress = task_info.get('progress', progress)
                        status_message = task_info.get('status', status_message)
                    elif task_info is not None:
                        # Handle cases where info might be a string or other simple type
                        error_details = f"Failure Info: {str(task_info)[:500]}" # Truncate potentially long strings
                    else:
                        error_details = "Task failed with unknown error details."

                    # Check result field for potential metadata if info was lacking
                    if isinstance(task_result_on_fail, dict):
                        progress = task_result_on_fail.get('progress', progress)
                        status_message = task_result_on_fail.get('status', status_message)
                        # Append result content if error details were poor
                        if not error_details or "unknown error" in error_details:
                             error_details += f" | Result Field: {str(task_result_on_fail)[:200]}"

                except (KeyError, TypeError, Exception) as e:
                    logger.error(f"Error retrieving failure details for task {task_id}: {e}", exc_info=True)
                    error_details = f"Task failed, error details retrieval failed: {type(e).__name__}"
                finally:
                    if error_details is None: # Ensure some message is set
                        error_details = "Task failed with unspecified error."


            elif task_state_str in [TaskStatusEnum.STARTED.value, TaskStatusEnum.RECEIVED.value, TaskStatusEnum.RETRY.value]:
                try:
                    task_info = async_result.info
                    if isinstance(task_info, dict):
                        progress = task_info.get('progress', progress)
                        status_message = task_info.get('status', status_message)
                    else:
                        logger.warning(f"Task {task_id} in state {task_state_str} has non-dict info: {type(task_info)}")
                except Exception as e:
                    logger.warning(f"Error accessing info for intermediate state task {task_id}: {e}", exc_info=True)

            elif task_state_str == TaskStatusEnum.REVOKED.value:
                 status_message = "Task was revoked."

            # Add handling for other potential Celery states if needed

        except Exception as outer_e:
             # Catch errors during AsyncResult interaction itself
             logger.error(f"Unexpected error processing task {task_id} state '{task_state_str}': {outer_e}", exc_info=True)
             if task_state_str == JobStatusEnum.FAILED and error_details is None:
                 error_details = f"Task failed, error processing status: {str(outer_e)[:100]}"
             elif status_message is None:
                 status_message = f"Error processing task status: {str(outer_e)[:100]}"


        # --- Map Celery state string to our Enum ---
        try:
            # Use the string value from Celery directly for enum lookup
            status_enum = schemas.TaskStatusEnum(task_state_str)
        except ValueError:
            logger.warning(f"Unknown Celery task state '{task_state_str}' for task {task_id}. Defaulting to PENDING.")
            status_enum = schemas.TaskStatusEnum.PENDING


        return schemas.TaskStatusResponse(
            task_id=task_id,
            status=status_enum,
            progress=progress,
            status_message=status_message,
            result=final_result,
            error=error_details,
        )

# --- Service Instantiation (Choose one approach) ---

# Option 1: Simple Global Instance (Easiest for now)
# Import the actual Celery app instance used by the backend to send tasks
from app.core.celery_app import backend_celery_app as celery_app_instance
task_status_service = TaskStatusService(celery_app_instance)

# Option 2: FastAPI Dependency (More complex, better for testability if service needs state)
# def get_task_status_service() -> TaskStatusService:
#    # This might involve getting celery_app from app state or a global
#    from app.core.celery_app import backend_celery_app as celery_app_instance
#    return TaskStatusService(celery_app_instance)