# shared/repositories/bot_pattern_repository.py
import logging
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.exc import SQLAlchemyError

from shared.db.models import BotPattern
from shared.schemas.bot_pattern import BotPatternCreate, BotPatternUpdate

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class BotPatternRepository(BaseRepository[BotPattern]):
    """Handles synchronous database operations for BotPattern."""

    def get_by_id(self, pattern_id: int) -> Optional[BotPattern]:
        """Get a single bot pattern by ID."""
        with self._session_scope() as session:
            return session.get(BotPattern, pattern_id)

    def get_patterns(
        self,
        repository_id: Optional[int] = None,
        include_global: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[Sequence[BotPattern], int]:
        """
        Get bot patterns, optionally filtered by repository, including global ones.
        Returns a tuple of (items, total_count).
        """
        with self._session_scope() as session:
            stmt_items = select(BotPattern)
            filters: List[ColumnElement[bool]] = []

            if repository_id is not None:
                repo_specific_filter = BotPattern.repository_id == repository_id
                if include_global:
                    filters.append(
                        or_(repo_specific_filter, BotPattern.repository_id.is_(None))
                    )
                else:
                    filters.append(repo_specific_filter)
            else:  # No repository_id specified, assume we want only global patterns
                filters.append(BotPattern.repository_id.is_(None))

            if filters:
                stmt_items = stmt_items.where(*filters)
                count_stmt = select(func.count(BotPattern.id)).where(*filters)
            else:
                count_stmt = select(func.count(BotPattern.id))

            total_result = session.execute(count_stmt)
            total = total_result.scalar_one()

            # Order by repo ID (nulls last for global) then by ID
            stmt = (
                stmt_items.order_by(BotPattern.repository_id.nullslast(), BotPattern.id)
                .offset(skip)
                .limit(limit)
            )
            items = session.execute(stmt).scalars().all()

            return items, total

    def create(self, obj_in: BotPatternCreate) -> BotPattern:
        """Create a new bot pattern (can be global or repo-specific)."""
        with self._session_scope() as session:
            try:
                db_obj = BotPattern(**obj_in.model_dump())
                session.add(db_obj)
                session.commit()
                session.refresh(db_obj)
                logger.info(
                    f"Created bot pattern ID {db_obj.id} for repo {db_obj.repository_id or 'Global'}"
                )
                return db_obj
            except SQLAlchemyError as e:
                logger.error(
                    f"BotPatternRepository: DB error creating pattern: {e}",
                    exc_info=True,
                )
                session.rollback()
                raise
            except Exception as e:
                logger.error(
                    f"BotPatternRepository: Unexpected error creating pattern: {e}",
                    exc_info=True,
                )
                session.rollback()
                raise

    def update(self, db_obj: BotPattern, obj_in: BotPatternUpdate) -> BotPattern:
        """Update an existing bot pattern."""
        with self._session_scope() as session:
            try:
                if db_obj not in session:
                    db_obj = session.merge(db_obj)
                update_data = obj_in.model_dump(exclude_unset=True)
                for field, value in update_data.items():
                    if hasattr(db_obj, field):
                        setattr(db_obj, field, value)
                session.add(db_obj)
                session.commit()
                session.refresh(db_obj)
                logger.info(f"Updated bot pattern ID {db_obj.id}")
                return db_obj
            except SQLAlchemyError as e:
                logger.error(
                    f"BotPatternRepository: DB error updating pattern {db_obj.id}: {e}",
                    exc_info=True,
                )
                session.rollback()
                raise
            except Exception as e:
                logger.error(
                    f"BotPatternRepository: Unexpected error updating pattern {db_obj.id}: {e}",
                    exc_info=True,
                )
                session.rollback()
                raise

    def delete(self, pattern_id: int) -> bool:
        """Delete a bot pattern by ID. Returns True if deleted."""
        with self._session_scope() as session:
            try:
                db_obj = session.get(BotPattern, pattern_id)
                if db_obj:
                    pattern_repo_id = db_obj.repository_id
                    session.delete(db_obj)
                    session.commit()
                    logger.info(
                        f"Deleted bot pattern ID {pattern_id} for repo {pattern_repo_id or 'Global'}"
                    )
                    return True
                else:
                    logger.warning(
                        f"Bot pattern ID {pattern_id} not found for deletion."
                    )
                    return False
            except SQLAlchemyError as e:
                logger.error(
                    f"BotPatternRepository: DB error deleting pattern {pattern_id}: {e}",
                    exc_info=True,
                )
                session.rollback()
                raise
            except Exception as e:
                logger.error(
                    f"BotPatternRepository: Unexpected error deleting pattern {pattern_id}: {e}",
                    exc_info=True,
                )
                session.rollback()
                raise
