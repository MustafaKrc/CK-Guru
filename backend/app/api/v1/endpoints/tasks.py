# backend/app/api/v1/endpoints/tasks.py
import logging
from typing import Any, Optional # Import Any for result type hint

from fastapi import APIRouter, HTTPException, status, Depends
from celery.result import AsyncResult

from app import schemas # Use schemas module directly
from app.core.celery_app import backend_celery_app as celery_app # Import the Celery app instance

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get(
    "/{task_id}",
    response_model=schemas.TaskStatusResponse,
    summary="Get task status and result",
    description="Poll this endpoint to check the status of a background task.",
    responses={
        404: {"description": "Task not found"},
    },
)
async def get_task_status(task_id: str):
    """
    Retrieve the status and result (if available) of a Celery task,
    including intermediate progress information.
    """
    task_result = AsyncResult(task_id, app=celery_app)

    final_result: Any | None = None
    error: str | None = None
    progress: Optional[int] = None
    status_message: Optional[str] = None

    task_state = task_result.state

    if task_state == 'PENDING':
        pass # Default values are None
    elif task_state == 'FAILURE':
        error = str(task_result.info) # task_result.info contains exception info
        # Attempt to get original metadata if stored before failure (depends on task logic)
        try:
            # Celery might store the exception instance or a dict representation
            if isinstance(task_result.info, dict) and 'exc_message' in task_result.info:
                 error = str(task_result.info.get('exc_message', error))
            # Check if result field holds last meta before failure (less common)
            if isinstance(task_result.result, dict):
                 progress = task_result.result.get('progress')
                 status_message = task_result.result.get('status')
        except Exception:
             logger.warning(f"Could not extract metadata from failed task {task_id} info.", exc_info=True)
    elif task_state == 'SUCCESS':
        final_result = task_result.result # This is the return value of the task
        # You might want to extract progress/status from the final result dict too
        if isinstance(final_result, dict):
            status_message = final_result.get('status')
            # Set progress to 100 on success? or leave as None? Let's leave as None unless explicitly set to 100 by task
            # progress = 100
    elif task_state == 'STARTED' or task_state == 'RECEIVED' or task_state == 'RETRY':
        # For intermediate states, the metadata is usually in task_result.info
        # Note: Celery versions/configs might place it in .result sometimes. .info is generally safer.
        if isinstance(task_result.info, dict):
            progress = task_result.info.get('progress')
            status_message = task_result.info.get('status')
        else:
             # Log if info isn't the expected dictionary
             logger.warning(f"Task {task_id} in state {task_state} has non-dict info: {task_result.info}")

    # Map Celery state string to our Enum
    try:
        status_enum = schemas.TaskStatusEnum(task_state)
    except ValueError:
        logger.warning(f"Unknown Celery task state '{task_state}' for task {task_id}. Falling back to PENDING.")
        status_enum = schemas.TaskStatusEnum.PENDING

    return schemas.TaskStatusResponse(
        task_id=task_id,
        status=status_enum,
        progress=progress,          
        status_message=status_message, 
        result=final_result,        
        error=error,
    )