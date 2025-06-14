# backend/app/crud/crud_repository.py
import logging
from typing import Optional, Sequence, Tuple
from urllib.parse import urlparse

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from shared.core.config import settings
from shared.db.models import BotPattern, Dataset, GitHubIssue, Repository
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
    """Get a single repository by ID, including relationship counts."""
    # Aliases for subqueries
    dataset_alias = aliased(Dataset)
    bot_pattern_alias = aliased(BotPattern)
    github_issue_alias = aliased(GitHubIssue)

    # Subqueries to count related items
    dataset_count_subquery = (
        select(func.count(dataset_alias.id))
        .where(dataset_alias.repository_id == Repository.id)
        .label("datasets_count")
    )
    bot_pattern_count_subquery = (
        select(func.count(bot_pattern_alias.id))
        .where(bot_pattern_alias.repository_id == Repository.id)
        .label("bot_patterns_count")
    )
    github_issue_count_subquery = (
        select(func.count(github_issue_alias.id))
        .where(github_issue_alias.repository_id == Repository.id)
        .label("github_issues_count")
    )

    stmt = select(
        Repository,
        dataset_count_subquery,
        bot_pattern_count_subquery,
        github_issue_count_subquery,
    ).filter(Repository.id == repo_id)

    result = await db.execute(stmt)
    repo_data = result.first()

    if repo_data:
        repo, datasets_count, bot_patterns_count, github_issues_count = repo_data
        # Manually attach counts to the ORM object for the Pydantic schema
        repo.datasets_count = datasets_count
        repo.bot_patterns_count = bot_patterns_count
        repo.github_issues_count = github_issues_count
        return repo

    return None


async def get_repository_by_git_url(
    db: AsyncSession, git_url: str
) -> Optional[Repository]:
    """Get a single repository by its Git URL."""

    stmt = select(Repository).filter(Repository.git_url == git_url)
    result = await db.execute(stmt)
    repo = result.scalars().first()

    return repo


async def get_repositories(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    q: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: str = "desc",
) -> Tuple[Sequence[Repository], int]:
    """Get multiple repositories with filtering, sorting, and pagination."""

    # Aliases for subqueries
    dataset_alias = aliased(Dataset)
    bot_pattern_alias = aliased(BotPattern)
    github_issue_alias = aliased(GitHubIssue)

    # Subqueries to count related items
    dataset_count_subquery = (
        select(func.count(dataset_alias.id))
        .where(dataset_alias.repository_id == Repository.id)
        .correlate(Repository)
        .scalar_subquery()
    )
    bot_pattern_count_subquery = (
        select(func.count(bot_pattern_alias.id))
        .where(bot_pattern_alias.repository_id == Repository.id)
        .correlate(Repository)
        .scalar_subquery()
    )
    github_issue_count_subquery = (
        select(func.count(github_issue_alias.id))
        .where(github_issue_alias.repository_id == Repository.id)
        .correlate(Repository)
        .scalar_subquery()
    )

    # Base statement with counts
    stmt = select(
        Repository,
        dataset_count_subquery.label("datasets_count"),
        bot_pattern_count_subquery.label("bot_patterns_count"),
        github_issue_count_subquery.label("github_issues_count"),
    )

    # Filtering
    if q:
        stmt = stmt.filter(Repository.name.ilike(f"%{q}%"))

    # Sorting
    if sort_by:
        sort_column = getattr(Repository, sort_by, None)
        if sort_column is not None:
            stmt = stmt.order_by(
                desc(sort_column) if sort_order == "desc" else asc(sort_column)
            )
    else:
        stmt = stmt.order_by(Repository.created_at.desc())

    # Count total matching items before pagination
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one_or_none() or 0

    # Apply pagination
    stmt = stmt.offset(skip).limit(limit)

    result_items = await db.execute(stmt)

    items = []
    for row in result_items:
        repo, datasets_count, bot_patterns_count, github_issues_count = row
        # Manually attach counts to the ORM object for the Pydantic schema
        repo.datasets_count = datasets_count
        repo.bot_patterns_count = bot_patterns_count
        repo.github_issues_count = github_issues_count
        items.append(repo)

    return items, total


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
