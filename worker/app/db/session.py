# worker/app/db/session.py
import logging
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from typing import AsyncGenerator

# Import settings from the worker's core config
from ..core.config import settings

logger = logging.getLogger(__name__)

if not settings.DATABASE_URL:
    logger.error("DATABASE_URL is not configured in worker settings!")
    # Decide how to handle: raise error, exit, or disable DB features?
    # For this workflow, it's essential, so raising an error is appropriate.
    raise ValueError("Worker requires DATABASE_URL to be configured for saving metrics.")

try:
    # Create the async engine
    async_engine = create_async_engine(
        str(settings.DATABASE_URL),
        pool_pre_ping=True,
        # Adjust pool size if needed under heavy load
        # pool_size=10,
        # max_overflow=20,
    )

    # Create the async session factory
    AsyncSessionLocal = async_sessionmaker(
        bind=async_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False, # Important for background tasks
        class_=AsyncSession
    )
    logger.info("Worker database session factory configured successfully.")

except Exception as e:
    logger.error(f"Failed to configure worker database engine/session: {e}", exc_info=True)
    raise
@asynccontextmanager
async def get_worker_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides a transactional database session for worker tasks."""
    session: AsyncSession = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
        logger.debug("Worker DB session committed successfully.")
    except SQLAlchemyError as db_err:
        logger.error(f"Worker DB session error: {db_err}", exc_info=True)
        await session.rollback()
        logger.info("Worker DB session rolled back.")
        raise # Re-raise the database error
    except Exception as e:
         logger.error(f"Non-DB error during worker session: {e}", exc_info=True)
         await session.rollback() # Rollback even for non-DB errors within the block
         logger.info("Worker DB session rolled back due to non-DB error.")
         raise # Re-raise other exceptions
    finally:
        await session.close()
        logger.debug("Worker DB session closed.")