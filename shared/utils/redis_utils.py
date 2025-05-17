# shared/utils/redis_utils.py
import json
import logging
from typing import Any, Dict, Optional

import redis.asyncio as aioredis
from redis.asyncio.client import PubSub

from shared.core.config import settings # Assuming your Redis URL is in settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

# Global Redis connection pool (recommended for managing connections)
_redis_pool: Optional[aioredis.ConnectionPool] = None

async def get_redis_connection_pool() -> aioredis.ConnectionPool:
    """
    Initializes and returns a global asyncio Redis connection pool.
    Ensures that the pool is created only once.
    """
    global _redis_pool
    if _redis_pool is None:
        try:
            logger.info(f"Initializing Redis connection pool for URL: {settings.REDIS_URL}")
            # Ensure REDIS_URL is set in your .env and loaded into settings
            # Example: REDIS_URL=redis://localhost:6379/0
            _redis_pool = aioredis.ConnectionPool.from_url(
                str(settings.REDIS_URL), # Make sure settings.REDIS_URL is a string
                max_connections=settings.REDIS_MAX_CONNECTIONS, # Add to config if needed, default 10
                decode_responses=False # Important for pubsub binary data
            )
            # Test connection (optional, but good for startup verification)
            # async with aioredis.Redis(connection_pool=_redis_pool) as r:
            #     await r.ping()
            # logger.info("Successfully connected to Redis and pinged server.")
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection pool: {e}", exc_info=True)
            # Depending on your app's requirements, you might want to raise the exception
            # or handle it in a way that allows the app to start but with Redis disabled.
            raise ConnectionError(f"Could not connect to Redis: {e}") from e
    return _redis_pool

async def get_redis_client() -> aioredis.Redis:
    """
    Returns an asyncio Redis client instance from the global connection pool.
    """
    pool = await get_redis_connection_pool()
    return aioredis.Redis(connection_pool=pool)


async def publish_task_event(
    redis_client: aioredis.Redis,
    channel: str,
    event_data: Dict[str, Any]
) -> None:
    """
    Publishes a task event (dictionary) to the specified Redis Pub/Sub channel.
    The event_data dictionary will be JSON serialized.

    Args:
        redis_client: An active asyncio Redis client instance.
        channel: The Redis Pub/Sub channel name to publish to.
        event_data: A dictionary containing the event payload.
    """
    if not isinstance(event_data, dict):
        logger.error(f"Attempted to publish non-dict event_data to {channel}: {type(event_data)}")
        return

    try:
        message = json.dumps(event_data)
        await redis_client.publish(channel, message)
        logger.debug(f"Published to {channel}: TaskID {event_data.get('task_id')} Status {event_data.get('status')}")
    except TypeError as e: # Handles non-serializable data in event_data
        logger.error(f"TypeError serializing event_data for Redis publish on {channel}: {e}. Data: {event_data}", exc_info=True)
    except Exception as e:
        logger.error(f"Failed to publish event to Redis channel {channel}: {e}", exc_info=True)

# Example of how to use the publisher within a Celery task:
# async def my_celery_task():
#     r_client = await get_redis_client()
#     event_payload = {"task_id": "123", "status": "PROGRESS", "progress": 50}
#     await publish_task_event(r_client, settings.REDIS_TASK_EVENTS_CHANNEL, event_payload)
#     # IMPORTANT: Close the client if it's not managed by a pool's context manager
#     # or if get_redis_client() doesn't handle closing.
#     # If using a pool, often you don't explicitly close clients obtained directly from it.
#     # However, if get_redis_client creates a new connection each time, it should be closed.
#     # For pool-based, usually the pool manages connection lifecycle.
#     # await r_client.close() # If not using a global pool context for the client itself