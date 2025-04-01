# backend/app/api/v1/endpoints/tasks.py
from fastapi import APIRouter, HTTPException, status, Depends
from celery.result import AsyncResult
from typing import Any # Import Any for result type hint

from app.core.celery_app import backend_celery_app as celery_app # Import the Celery app instance
from app import schemas # Use schemas module directly

router = APIRouter()

@router.get(
    "/{task_id}",
    response_model=schemas.TaskStatusResponse,
    summary="Get task status and result",
    description="Poll this endpoint to check the status of a background task.",
    responses={
        404: {"description": "Task not found"},
        # Add other potential responses as needed
    },
)
async def get_task_status(task_id: str):
    """
    Retrieve the status and result (if available) of a Celery task.
    """
    # Use the imported celery_app instance
    task_result = AsyncResult(task_id, app=celery_app)

    result: Any | None = None
    error: str | None = None

    if task_result.state == 'PENDING':
        # Task state is PENDING if the task is unknown or waiting
        # Check if the task is known to the backend
        # Note: This check might depend on your result backend configuration.
        # If the task ID doesn't exist, Celery might still return PENDING.
        # A more robust check might involve querying your own DB if you store task IDs.
        # For now, we assume PENDING means waiting or unknown.
        pass # Keep result/error as None
    elif task_result.state == 'FAILURE':
        error = str(task_result.info) # Access the exception stored by Celery
        # task_result.info might contain the traceback as well, depending on config
    elif task_result.state == 'SUCCESS':
        result = task_result.result # Access the return value of the task

    # Handle unknown task ID slightly more explicitly if possible
    # This check is imperfect with default Celery backends.
    # if task_result.state == 'PENDING' and not task_result.backend:
       # raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found or backend not configured correctly")
    # A more reliable way requires storing task IDs yourself when created.

    # Map Celery state strings to our Enum if necessary, or ensure Celery states match Enum values
    try:
        status_enum = schemas.TaskStatusEnum(task_result.state)
    except ValueError:
        # Handle potential unknown states reported by Celery if they don't match your enum
        # Log this unexpected state
        # logger.warning(f"Unknown Celery task state '{task_result.state}' for task {task_id}")
        # Decide on fallback status, e.g., PENDING or a specific UNKNOWN status if added to enum
        status_enum = schemas.TaskStatusEnum.PENDING # Example fallback

    return schemas.TaskStatusResponse(
        task_id=task_id,
        status=status_enum,
        result=result,
        error=error,
    )