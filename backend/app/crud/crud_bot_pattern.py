# backend/app/crud/crud_bot_pattern.py
import logging
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.core.config import settings
from shared.db.models.bot_pattern import BotPattern
from shared.schemas.bot_pattern import BotPatternCreate, BotPatternUpdate

logger = logging.getLogger(__name__)

async def get_bot_pattern(db: AsyncSession, pattern_id: int) -> Optional[BotPattern]:
    """Get a single bot pattern by ID."""
    result = await db.execute(select(BotPattern).filter(BotPattern.id == pattern_id))
    return result.scalars().first()

async def get_bot_patterns(
    db: AsyncSession, *, repository_id: Optional[int] = None, include_global: bool = True, skip: int = 0, limit: int = 100
) -> Tuple[Sequence[BotPattern], int]:
    """Get bot patterns, optionally filtered by repository, including global ones."""
    stmt_items = select(BotPattern)
    filters: List[ColumnElement[bool]] = []

    if repository_id is not None:
        repo_specific_filter = (BotPattern.repository_id == repository_id)
        if include_global:
            filters.append(or_(repo_specific_filter, BotPattern.repository_id.is_(None)))
        else:
            filters.append(repo_specific_filter)
    else: # No repository_id means we are in a global context
        filters.append(BotPattern.repository_id.is_(None))

    if filters:
        stmt_items = stmt_items.where(*filters)

    # Count total items matching the filter
    stmt_total = select(func.count()).select_from(BotPattern).where(*filters) if filters else select(func.count(BotPattern.id))
    total_result = await db.execute(stmt_total)
    total = total_result.scalar_one()

    # Apply pagination and order
    stmt_items = stmt_items.order_by(BotPattern.id.desc()).offset(skip).limit(limit)
    items_result = await db.execute(stmt_items)
    items = items_result.scalars().all()
    
    return items, total

async def create_bot_pattern(db: AsyncSession, *, obj_in: BotPatternCreate) -> BotPattern:
    """Create a new bot pattern."""
    db_obj = BotPattern(**obj_in.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    logger.info(f"Created bot pattern ID {db_obj.id} for repo {db_obj.repository_id or 'Global'}")
    return db_obj

async def update_bot_pattern(db: AsyncSession, *, db_obj: BotPattern, obj_in: BotPatternUpdate) -> BotPattern:
    """Update an existing bot pattern."""
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    logger.info(f"Updated bot pattern ID {db_obj.id}")
    return db_obj

async def delete_bot_pattern(db: AsyncSession, *, pattern_id: int) -> Optional[BotPattern]:
    """Delete a bot pattern by ID."""
    db_obj = await get_bot_pattern(db, pattern_id=pattern_id)
    if db_obj:
        repo_id_log = db_obj.repository_id
        await db.delete(db_obj)
        await db.commit()
        logger.info(f"Deleted bot pattern ID {pattern_id} for repo {repo_id_log or 'Global'}")
    return db_obj