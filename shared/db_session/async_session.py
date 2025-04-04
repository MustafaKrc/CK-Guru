# shared/db_session/async_session.py
import logging
from typing import AsyncGenerator

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Use shared config
from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

if not settings.DATABASE_URL:
    logger.error("DATABASE_URL is not configured in settings!")
    # Backend likely needs this to start, so raise error
    raise ValueError("DATABASE_URL configuration is required.")

# --- Async Setup (Moved from backend) ---
try:
    # Create the async engine using the DATABASE_URL from shared settings
    async_engine = create_async_engine(
        str(settings.DATABASE_URL),
        pool_pre_ping=True, # Check connections before use
        echo=False         # Set echo=True for debugging SQL
    )

    # Create the async session factory
    AsyncSessionFactory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False, # Keep objects accessible after commit
        autoflush=False,        # We will manually flush when needed
    )
    logger.info("ASYNC database session factory configured.")

except Exception as e:
    logger.error(f"Failed to configure ASYNC database engine/session: {e}", exc_info=True)
    raise # Fail hard if DB cannot be configured

async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function for FastAPI that yields an async SQLAlchemy session.
    Ensures the session is closed afterwards.
    """
    logger.debug("Creating async DB session")
    async with AsyncSessionFactory() as session:
        try:
            yield session
            # Commits/rollbacks should be handled within the endpoint/CRUD layer
            # await session.commit() # Typically not committed here
        except SQLAlchemyError as db_err:
            logger.error(f"Async DB session error during request: {db_err}", exc_info=True)
            await session.rollback()
            # Re-raise the exception so FastAPI can handle it (e.g., return 500)
            raise
        except Exception:
             # Catch other exceptions, rollback, and re-raise
             await session.rollback()
             raise
        finally:
            # Session is automatically closed by the async context manager
             logger.debug("Async DB session closed")
            # pass # No explicit close needed