from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload # If needed for eager loading relationships later
from typing import List, Optional, Sequence
import re
import logging

from shared.db.models import Repository
from app.schemas.repository import RepositoryCreate, RepositoryUpdate

logger = logging.getLogger(__name__)

def _extract_repo_name(git_url: str) -> str:
    """Extracts a plausible repository name from a Git URL."""
    try:
        # Remove .git suffix if present
        name = re.sub(r'\.git$', '', git_url)
        # Get the last part of the path
        name = name.split('/')[-1]
        # Handle potential empty strings if URL ends with /
        if not name:
             name = git_url.split('/')[-2] # Try second to last
        return name
    except Exception as e:
        logger.error(f"Could not extract name from URL '{git_url}': {e}")
        return "unknown_repo" # Fallback name

async def get_repository(db: AsyncSession, repo_id: int) -> Optional[Repository]:
    """Get a single repository by ID."""
    result = await db.execute(select(Repository).filter(Repository.id == repo_id))
    return result.scalars().first()

async def get_repository_by_git_url(db: AsyncSession, git_url: str) -> Optional[Repository]:
    """Get a single repository by its Git URL."""
    result = await db.execute(select(Repository).filter(Repository.git_url == git_url))
    return result.scalars().first()

async def get_repositories(db: AsyncSession, skip: int = 0, limit: int = 100) -> Sequence[Repository]:
    """Get multiple repositories with pagination."""
    result = await db.execute(
        select(Repository)
        .order_by(Repository.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def create_repository(db: AsyncSession, *, obj_in: RepositoryCreate) -> Repository:
    """Create a new repository."""
    repo_name = _extract_repo_name(str(obj_in.git_url))
    db_obj = Repository(
        git_url=str(obj_in.git_url), # Convert HttpUrl back to string for DB
        name=repo_name
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def update_repository(db: AsyncSession, *, db_obj: Repository, obj_in: RepositoryUpdate) -> Repository:
    """Update an existing repository."""
    update_data = obj_in.model_dump(exclude_unset=True) # Use Pydantic V2 method
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def delete_repository(db: AsyncSession, *, repo_id: int) -> Optional[Repository]:
   """Delete a repository by ID."""
   db_obj = await get_repository(db, repo_id)
   if db_obj:
       await db.delete(db_obj)
       await db.commit()
   return db_obj