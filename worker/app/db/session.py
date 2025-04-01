# worker/app/db/session.py
import logging
from contextlib import asynccontextmanager, contextmanager # Add contextmanager
from sqlalchemy import create_engine # Add sync engine creator
from sqlalchemy.orm import sessionmaker # Add sync sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from ..core.config import settings

logger = logging.getLogger(__name__)

if not settings.DATABASE_URL:
    logger.error("DATABASE_URL is not configured in worker settings!")
    raise ValueError("Worker requires DATABASE_URL.")

# --- Async Setup ---
try:
    async_engine = create_async_engine(
        str(settings.DATABASE_URL), pool_pre_ping=True
    )
    AsyncSessionLocal = async_sessionmaker(
        bind=async_engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=AsyncSession
    )
    logger.info("Worker ASYNC database session factory configured.")
except Exception as e:
    logger.error(f"Failed to configure worker ASYNC database engine/session: {e}", exc_info=True)
    raise

@asynccontextmanager
async def get_worker_session() -> AsyncSession:
    """Provides a transactional database session for worker tasks."""

    session: AsyncSession = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except SQLAlchemyError as db_err:
        logger.error(f"Worker ASYNC DB session error: {db_err}", exc_info=True)
        await session.rollback()
        raise
    except Exception as e:
         logger.error(f"Non-DB error during worker ASYNC session: {e}", exc_info=True)
         await session.rollback()
         raise
    finally:
        await session.close()

# --- Synchronous Setup ---
try:
    # Create a synchronous engine using the same URL
    # Need to adjust the driver if DATABASE_URL uses asyncpg specifically
    sync_db_url = str(settings.DATABASE_URL).replace("+asyncpg", "") # Use default psycopg2 driver usually
    sync_engine = create_engine(sync_db_url, pool_pre_ping=True)

    # Create a synchronous session factory
    SyncSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=sync_engine
    )
    logger.info("Worker SYNC database session factory configured.")
except Exception as e:
    logger.error(f"Failed to configure worker SYNC database engine/session: {e}", exc_info=True)
    # Decide if this is fatal; maybe sync access isn't strictly required everywhere
    # raise # Or just log the error

@contextmanager
def get_worker_sync_session(): # Non-async context manager
    """Provides a transactional synchronous database session."""
    session = None
    try:
        session = SyncSessionLocal()
        yield session
        session.commit()
        logger.debug("Worker SYNC DB session committed successfully.")
    except SQLAlchemyError as db_err:
        logger.error(f"Worker SYNC DB session error: {db_err}", exc_info=True)
        if session:
            session.rollback()
        raise
    except Exception as e:
        logger.error(f"Non-DB error during worker SYNC session: {e}", exc_info=True)
        if session:
             session.rollback()
        raise
    finally:
        if session:
            session.close()
            logger.debug("Worker SYNC DB session closed.")