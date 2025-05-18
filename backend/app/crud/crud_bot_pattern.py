# backend/app/crud/crud_bot_pattern.py
import logging
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import ColumnElement, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared.core.config import settings
from shared.db.models.bot_pattern import BotPattern
from shared.schemas.bot_pattern import BotPatternCreate, BotPatternUpdate

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


# --- Get Bot Patterns ---
async def get_bot_pattern(db: AsyncSession, pattern_id: int) -> Optional[BotPattern]:
    """Get a single bot pattern by ID."""
    result = await db.execute(select(BotPattern).filter(BotPattern.id == pattern_id))
    return result.scalars().first()


async def get_bot_patterns(
    db: AsyncSession,
    *,
    repository_id: Optional[int] = None,  # Filter by repo ID
    include_global: bool = True,  # Also include global patterns
    skip: int = 0,
    limit: int = 100,
) -> Tuple[Sequence[BotPattern], int]:
    """
    Get bot patterns, optionally filtered by repository, including global ones.
    Returns a tuple of (items, total_count).
    """
    stmt_items = select(BotPattern)
    filters: List[ColumnElement[bool]] = []

    if repository_id is not None:
        if include_global:
            # Get patterns specific to this repo OR global patterns
            filters.append(
                (BotPattern.repository_id == repository_id)
                | (BotPattern.repository_id.is_(None))
            )
        else:
            # Get patterns specific to this repo ONLY
            filters.append(BotPattern.repository_id == repository_id)
    elif not include_global:
        # Get only global patterns when no repo_id is specified
        filters.append(BotPattern.repository_id.is_(None))
    # else: get all patterns (repo-specific and global) if repo_id is None and include_global is True

    if filters:
        stmt_items = stmt_items.where(*filters)

    stmt_items = (
        stmt_items.order_by(BotPattern.repository_id.nullslast(), BotPattern.id)
        .offset(skip)
        .limit(limit)
    )  # Show global last
    result_items = await db.execute(stmt_items)
    items = result_items.scalars().all()

    # Query for total count
    stmt_total = select(func.count(BotPattern.id))
    if filters:
        stmt_total = stmt_total.where(*filters)

    result_total = await db.execute(stmt_total)
    total = result_total.scalar_one_or_none() or 0

    return items, total


# --- Create Bot Pattern ---
async def create_bot_pattern(
    db: AsyncSession, *, obj_in: BotPatternCreate
) -> BotPattern:
    """Create a new bot pattern (can be global or repo-specific)."""
    # Ensure repository_id in obj_in is used correctly
    db_obj = BotPattern(**obj_in.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    logger.info(
        f"Created bot pattern ID {db_obj.id} for repo {db_obj.repository_id or 'Global'}"
    )
    return db_obj


# --- Update Bot Pattern ---
async def update_bot_pattern(
    db: AsyncSession,
    *,
    db_obj: BotPattern,  # The existing object fetched via get_bot_pattern
    obj_in: BotPatternUpdate,
) -> BotPattern:
    """Update an existing bot pattern."""
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    db.add(db_obj)  # Add the modified object to the session
    await db.commit()
    await db.refresh(db_obj)
    logger.info(f"Updated bot pattern ID {db_obj.id}")
    return db_obj


# --- Delete Bot Pattern ---
async def delete_bot_pattern(
    db: AsyncSession, *, pattern_id: int
) -> Optional[BotPattern]:
    """Delete a bot pattern by ID."""
    db_obj = await get_bot_pattern(db, pattern_id=pattern_id)
    if db_obj:
        pattern_repo_id = db_obj.repository_id  # Store before delete
        await db.delete(db_obj)
        await db.commit()
        logger.info(
            f"Deleted bot pattern ID {pattern_id} for repo {pattern_repo_id or 'Global'}"
        )
    return db_obj
