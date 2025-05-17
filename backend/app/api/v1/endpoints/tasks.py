# backend/app/api/v1/endpoints/tasks.py
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict  # Import Any for result type hint

from celery.exceptions import CeleryError
from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, Query, status, Depends, Request
from sse_starlette.sse import EventSourceResponse 

# Import Celery app for revoke endpoint
from app.core.celery_app import backend_celery_app as celery_app

# Import the TaskStatusService
from app.services.task_status_service import (  # Using Option 1 (Global Instance)
    task_status_service,
)
from shared import schemas
from shared.core.config import settings
from shared.utils.redis_utils import get_redis_client
import redis.asyncio as aioredis


logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

router = APIRouter()

    
async def task_event_generator(request: Request, redis_client: aioredis.Redis):
    """
    Generator function that subscribes to Redis Pub/Sub and yields
    SSE formatted events for task updates.
    """
    # Ensure TASK_EVENTS_CHANNEL is correctly sourced, e.g., from settings
    channel_name = settings.REDIS_TASK_EVENTS_CHANNEL
    
    # Check initial connection (optional, but good for early exit)
    if not await request.is_disconnected():
         logger.info(f"SSE client connected. Subscribing to Redis channel: {channel_name}")
    
    async with redis_client.pubsub() as pubsub:
        await pubsub.subscribe(channel_name)
        try:
            while True:
                if await request.is_disconnected():
                    logger.info(f"SSE client disconnected from {channel_name}.")
                    break # Exit loop if client disconnects

                # Wait for a message with a timeout to allow checking request.is_disconnected()
                # and sending heartbeats periodically.
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True, timeout=None), # Set timeout if you want to send heartbeats more frequently than messages arrive
                        timeout=settings.SSE_HEARTBEAT_INTERVAL # e.g., 20 seconds from settings
                    )
                except asyncio.TimeoutError:
                    # No message from Redis, send a heartbeat
                    heartbeat_data = {"type": "heartbeat", "timestamp": datetime.now(timezone.utc).isoformat()}
                    # SSE comment format for heartbeat:
                    # yield f": {json.dumps(heartbeat_data)}\n\n"
                    # Or sse-starlette format:
                    yield {"event": "heartbeat", "data": json.dumps(heartbeat_data)}
                    continue # Go back to check for messages or disconnect

                if message and message.get("type") == "message":
                    event_data_str = message["data"].decode('utf-8') # Redis pubsub data is bytes
                    # Here, you could add filtering logic if task events contain user_id
                    # and you have the current_user from an auth dependency.
                    # For example:
                    # event_payload = json.loads(event_data_str)
                    # if event_payload.get("user_id") == current_user.id:
                    #     yield {"event": "task_update", "data": event_data_str}
                    
                    logger.debug(f"SSE: Sending event 'task_update' with data: {event_data_str[:200]}...") # Log snippet
                    yield {"event": "task_update", "data": event_data_str}
                
                # A small sleep to prevent a very tight loop if Redis is extremely active
                # or if get_message had no timeout. With timeout on get_message, this might be less critical.
                # await asyncio.sleep(0.01) 

        except asyncio.CancelledError:
            logger.info(f"SSE event generator for {channel_name} was cancelled.")
        except Exception as e:
            logger.error(f"Error in SSE event generator for {channel_name}: {e}", exc_info=True)
        finally:
            logger.info(f"SSE client unsubscribing from {channel_name}.")
            # Ensure unsubscription even if client didn't disconnect gracefully
            # but loop was broken by an error.
            try:
                await pubsub.unsubscribe(channel_name)
            except Exception as unsub_e:
                logger.error(f"Error unsubscribing from Redis channel {channel_name}: {unsub_e}")

@router.get(
    "/stream-updates", # Path is /api/v1/tasks/stream-updates due to router prefix
    summary="Stream real-time task status updates via SSE",
    response_class=EventSourceResponse # Correct response class for SSE
)
async def stream_task_updates_endpoint(
    request: Request, # FastAPI injects the request object
    redis_client: aioredis.Redis = Depends(get_redis_client) # Use your actual dependency
    # current_user: User = Depends(get_current_active_user), # Add when auth is ready
):
    """
    Endpoint for Server-Sent Events (SSE) to stream task status updates.
    Clients connect here to receive real-time updates on background tasks.
    Requires client to handle 'task_update' and 'heartbeat' events.
    """

    print(f"stream_task_updates_endpoint called with request: {request}")
    if not redis_client:
        logger.error("SSE stream_task_updates: Redis client dependency failed.")
        raise HTTPException(status_code=503, detail="Redis service unavailable for SSE.")
    
    # Pass current_user to generator if/when auth is added and filtering is needed
    return EventSourceResponse(task_event_generator(request, redis_client))

# this endpoint must be defined after the stream_task_updates_endpoint
# to avoid conflicts with the path
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
