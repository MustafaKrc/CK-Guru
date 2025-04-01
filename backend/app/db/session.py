from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from typing import AsyncGenerator

# Create the async engine
async_engine = create_async_engine(
    str(settings.DATABASE_URL), # Use the string representation
    pool_pre_ping=True,         # Check connections before use
    echo=False                  # Set to True for debugging SQL queries
)

# Create the async session factory
AsyncSessionFactory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,     # Keep objects accessible after commit
    autoflush=False,            # We will manually flush when needed
)
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function that yields an async SQLAlchemy session.
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            # Optional: await session.commit() # If you want auto-commit (usually not recommended with explicit CRUD)
        except Exception:
            await session.rollback()
            raise
        finally:
            # The context manager ensures session.close() is called
            pass # No explicit close needed with async context manager
        