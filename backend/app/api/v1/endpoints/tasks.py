# backend/app/api/v1/endpoints/tasks.py
import logging
from typing import Dict  # Import Any for result type hint

# Import Celery app for revoke endpoint
from app.core.celery_app import backend_celery_app as celery_app

# Import the TaskStatusService
from app.services.task_status_service import (  # Using Option 1 (Global Instance)
    task_status_service,
)
from celery.exceptions import CeleryError
from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, Query, status

from shared import schemas
from shared.core.config import settings

# If using Option 2 (Depends):
# from app.services.task_status_service import TaskStatusService, get_task_status_service


logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

router = APIRouter()


@router.get(
    "/{task_id}",
    response_model=schemas.TaskStatusResponse,
    summary="Get task status and result",
    description="Poll this endpoint to check the status of a background task.",
    responses={
        404: {"description": "Task not found (or backend has no info)"},
        500: {"description": "Internal server error retrieving status"},
    },
)
async def get_task_status(
    task_id: str,
    # If using Depends: service: TaskStatusService = Depends(get_task_status_service)
):
    """
    Retrieve the status and result (if available) of a Celery task,
    using the TaskStatusService for robust handling.
    """
    try:
        # Delegate to the service
        response = task_status_service.get_status(task_id)
        # Optional: Check if AsyncResult itself indicated task not found,
        # although the service might handle this internally by returning PENDING.
        # For now, assume service returns a valid response object.
        return response
    except Exception as e:
        # Catch unexpected errors during service interaction
        logger.error(
            f"Error getting status for task {task_id} via service: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve task status.",
        )


@router.post(
    "/{task_id}/revoke",
    response_model=Dict[str, str],  # Return simple message dict
    status_code=status.HTTP_202_ACCEPTED,  # Accepted for processing
    summary="Revoke/Terminate a Task",
    description="Attempts to stop a pending or running task. Uses SIGTERM for termination by default.",
    responses={
        500: {"description": "Failed to send revoke command"},
        400: {"description": "Invalid signal specified"},
        404: {
            "description": "Task backend might not know this ID (but revoke sent anyway)"
        },  # Revoke can be sent even for unknown IDs
    },
)
async def revoke_task(
    task_id: str,
    terminate: bool = Query(
        True,
        description="If true, attempt to terminate the running task process (SIGTERM). If false, just prevent pending task from starting or ignore result if running.",
    ),
    signal: str = Query(
        "TERM",
        description="Signal to use for termination (e.g., TERM, KILL). Only used if terminate=True.",
    ),
):
    """
    Sends a revoke command to Celery for the given task ID.
    By default, it attempts to terminate the task process using SIGTERM.
    """
    logger.info(
        f"Received request to revoke task ID: {task_id} (terminate={terminate}, signal={signal})"
    )

    # Validate signal if terminating
    valid_signals = ["TERM", "KILL"]  # Common signals, add others if needed
    if terminate and signal.upper() not in valid_signals:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid signal '{signal}'. Valid signals are: {', '.join(valid_signals)}",
        )

    try:
        # Get AsyncResult object to call revoke
        # Note: This doesn't guarantee the task exists from the backend's perspective *yet*,
        # but the revoke command can still be sent to the broker/workers.
        task_result = AsyncResult(task_id, app=celery_app)

        # Send the revoke command
        task_result.revoke(terminate=terminate, signal=signal.upper())

        logger.info(f"Revoke command sent for task ID: {task_id}")
        return {
            "message": f"Revoke command sent for task {task_id}. State may take time to update."
        }

    except CeleryError as e:
        # Catch potential errors communicating with the broker/backend when sending revoke
        logger.error(
            f"Celery error while sending revoke for task {task_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send revoke command due to a Celery communication error: {e}",
        )
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(
            f"Unexpected error during revoke for task {task_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}",
        )
