from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionFactory

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function that yields an async SQLAlchemy session.
    Ensures the session is closed afterwards.
    """
    async with AsyncSessionFactory() as session:
        yield session
        # No commit/rollback here usually, handled in CRUD or service layer explicitly
        # Or rely on context manager exception handling for rollback

# Add other dependencies here later (e.g., get_current_user)
