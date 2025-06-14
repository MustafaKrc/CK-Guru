# shared/db_session/sync_session.py
import logging
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as SqlaSession  # Rename Session to avoid conflict
from sqlalchemy.orm import sessionmaker

from shared.core.config import settings  # Use shared config

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

if not settings.DATABASE_URL:
    logger.error("DATABASE_URL is not configured in settings!")
    # Decide how critical this is at import time. Maybe workers can start without DB?
    # For now, let's raise
    raise ValueError("DATABASE_URL configuration is required.")

# Create sync engine based on DATABASE_URL
try:
    sync_db_url = str(settings.DATABASE_URL).replace(
        "+asyncpg", ""
    )  # Assume sync driver needed is psycopg2
    sync_engine = create_engine(
        sync_db_url, pool_pre_ping=True, echo=False
    )  # Set echo=True for debugging SQL
    SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
    logger.info("SYNC database session factory configured.")
except Exception as e:
    logger.error(
        f"Failed to configure SYNC database engine/session: {e}", exc_info=True
    )
    raise  # Fail hard if DB cannot be configured


@contextmanager
def get_sync_db_session() -> Generator[SqlaSession, None, None]:
    """Provides a transactional synchronous database session for workers."""
    session: Optional[SqlaSession] = None
    try:
        session = SyncSessionLocal()
        yield session
        session.commit()
        logger.debug("SYNC DB session committed successfully.")
    except SQLAlchemyError as db_err:
        logger.error(f"SYNC DB session error: {db_err}", exc_info=True)
        if session:
            session.rollback()
        raise
    except Exception as e:
        logger.error(f"Non-DB error during SYNC session: {e}", exc_info=True)
        if session:
            session.rollback()
        raise
    finally:
        if session:
            session.close()
            logger.debug("SYNC DB session closed.")
