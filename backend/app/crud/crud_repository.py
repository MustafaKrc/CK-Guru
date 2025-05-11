# backend/app/crud/crud_repository.py
import logging
from typing import Optional, Sequence
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.core.config import settings
from shared.db.models import Repository
from shared.schemas.repository import RepositoryCreate, RepositoryUpdate

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


def _extract_repo_name(git_url: str) -> str:
    """Extracts a plausible repository name from a Git URL."""
    try:
        # Handle protocol if present (e.g., git@host:path)
        if ":" in git_url and "@" in git_url.split(":")[0]:
            path_part = git_url.split(":")[-1]
        else:
            # Handle http/https URLs
            parsed_url = urlparse(git_url)
            path_part = parsed_url.path

        # Remove leading/trailing slashes and .git suffix
        cleaned_path = path_part.strip("/").replace(".git", "")

        if not cleaned_path:  # If nothing remains after cleaning
            return "unknown_repo"

        # Get the last component of the path
        name = cleaned_path.split("/")[-1]

        if not name:  # If the last component was empty (e.g. from trailing slash)
            return "unknown_repo"

        return name
    except Exception as e:
        logger.error(f"Could not extract name from URL '{git_url}': {e}")
        return "unknown_repo"  # Fallback name


async def get_repository(db: AsyncSession, repo_id: int) -> Optional[Repository]:
    """Get a single repository by ID."""
    result = await db.execute(select(Repository).filter(Repository.id == repo_id))
    return result.scalars().first()


async def get_repository_by_git_url(
    db: AsyncSession, git_url: str
) -> Optional[Repository]:
    """Get a single repository by its Git URL."""
    # Normalize URL slightly? Maybe remove trailing .git? Be careful.
    # Let's assume exact match for now.
    normalized_url = (
        git_url.removesuffix(".git") if git_url.endswith(".git") else git_url
    )
    # Query using both original and potentially normalized versions if needed, or stick to one.
    # Sticking to exact match based on schema for now.
    stmt = select(Repository).filter(Repository.git_url == git_url)
    result = await db.execute(stmt)
    repo = result.scalars().first()
    # Optional: If not found with exact match, try normalized?
    # if not repo and normalized_url != git_url:
    #     stmt_norm = select(Repository).filter(Repository.git_url == normalized_url)
    #     result_norm = await db.execute(stmt_norm)
    #     repo = result_norm.scalars().first()
    #     if repo: logger.debug(f"Found repo using normalized URL {normalized_url}")

    return repo


async def get_repositories(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> Sequence[Repository]:
    """Get multiple repositories with pagination."""
    result = await db.execute(
        select(Repository)
        .order_by(Repository.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


async def create_repository(
    db: AsyncSession, *, obj_in: RepositoryCreate
) -> Repository:
    """Create a new repository."""
    repo_name = _extract_repo_name(str(obj_in.git_url))
    db_obj = Repository(
        git_url=str(obj_in.git_url),  # Convert HttpUrl back to string for DB
        name=repo_name,
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def update_repository(
    db: AsyncSession, *, db_obj: Repository, obj_in: RepositoryUpdate
) -> Repository:
    """Update an existing repository."""
    update_data = obj_in.model_dump(exclude_unset=True)  # Use Pydantic V2 method
    for field, value in update_data.items():
        # Handle HttpUrl conversion back to string if git_url is updated
        if field == "git_url" and value is not None:
            setattr(db_obj, field, str(value))
        elif value is not None:  # Avoid setting None explicitly unless intended
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
