# shared/repositories/bot_pattern_repository.py
import logging
from typing import Sequence, List, Optional, Type

import sqlalchemy as sa
from sqlalchemy import select, delete, ColumnElement, or_
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.exc import SQLAlchemyError

from shared.db.models.bot_pattern import PatternTypeEnum

from .base_repository import BaseRepository
from shared.db.models import BotPattern
from shared.schemas.bot_pattern import BotPatternCreate, BotPatternUpdate

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
        limit: int = 100
    ) -> Sequence[BotPattern]:
        """Get bot patterns, optionally filtered by repository, including global ones."""
        with self._session_scope() as session:
            stmt = select(BotPattern)
            filters: List[ColumnElement[bool]] = []

            if repository_id is not None:
                if include_global:
                    filters.append(or_(BotPattern.repository_id == repository_id, BotPattern.repository_id.is_(None)))
                else:
                    filters.append(BotPattern.repository_id == repository_id)
            elif not include_global: # Get only global patterns when no repo_id is specified
                 filters.append(BotPattern.repository_id.is_(None))
            # else: No repo_id, include_global=True -> no filters needed, select all

            if filters:
                stmt = stmt.where(*filters)

            # Order by repo ID (nulls last for global) then by ID
            stmt = stmt.order_by(BotPattern.repository_id.nullslast(), BotPattern.id).offset(skip).limit(limit)
            return session.execute(stmt).scalars().all()

    def create(self, obj_in: BotPatternCreate) -> BotPattern:
        """Create a new bot pattern (can be global or repo-specific)."""
        with self._session_scope() as session:
            try:
                db_obj = BotPattern(**obj_in.model_dump())
                session.add(db_obj)
                session.commit()
                session.refresh(db_obj)
                logger.info(f"Created bot pattern ID {db_obj.id} for repo {db_obj.repository_id or 'Global'}")
                return db_obj
            except SQLAlchemyError as e:
                logger.error(f"BotPatternRepository: DB error creating pattern: {e}", exc_info=True)
                raise
            except Exception as e:
                logger.error(f"BotPatternRepository: Unexpected error creating pattern: {e}", exc_info=True)
                raise

    def update(self, db_obj: BotPattern, obj_in: BotPatternUpdate) -> BotPattern:
        """Update an existing bot pattern."""
        with self._session_scope() as session:
            try:
                if db_obj not in session: db_obj = session.merge(db_obj)
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
                logger.error(f"BotPatternRepository: DB error updating pattern {db_obj.id}: {e}", exc_info=True)
                raise
            except Exception as e:
                logger.error(f"BotPatternRepository: Unexpected error updating pattern {db_obj.id}: {e}", exc_info=True)
                raise

    def delete(self, pattern_id: int) -> bool:
        """Delete a bot pattern by ID. Returns True if deleted."""
        with self._session_scope() as session:
            try:
                db_obj = session.get(BotPattern, pattern_id)
                if db_obj:
                    pattern_repo_id = db_obj.repository_id # Store before delete
                    session.delete(db_obj)
                    session.commit()
                    logger.info(f"Deleted bot pattern ID {pattern_id} for repo {pattern_repo_id or 'Global'}")
                    return True
                else:
                    logger.warning(f"Bot pattern ID {pattern_id} not found for deletion.")
                    return False
            except SQLAlchemyError as e:
                logger.error(f"BotPatternRepository: DB error deleting pattern {pattern_id}: {e}", exc_info=True)
                raise
            except Exception as e:
                logger.error(f"BotPatternRepository: Unexpected error deleting pattern {pattern_id}: {e}", exc_info=True)
                raise
            

    @staticmethod
    def build_bot_filter_condition(
        bot_patterns: List[BotPattern],
        model_alias: Type[DeclarativeBase] # Use model alias (e.g., cgm_alias)
    ) -> Optional[ColumnElement[bool]]:
        """
        Builds an SQLAlchemy filter condition to identify bot authors based on patterns.

        Args:
            bot_patterns: A list of BotPattern ORM objects to use for filtering.
            model_alias: The SQLAlchemy aliased class representing the table with the 'author_name' column.

        Returns:
            An SQLAlchemy filter expression (ColumnElement), or None if no patterns are provided.
        """
        if not bot_patterns:
            return None # No filter needed

        inclusion_filters = []
        exclusion_filters = []
        try:
            # Get the 'author_name' column object from the provided alias
            col = getattr(model_alias, 'author_name')
        except AttributeError:
            logger.error(f"Model alias {model_alias} does not have an 'author_name' attribute.")
            return None # Cannot build filter without the column

        for bp in bot_patterns:
            filter_expr = None
            # Ensure bp.pattern is treated as string for operations
            pattern_str = str(bp.pattern)

            if bp.pattern_type == PatternTypeEnum.EXACT:
                filter_expr = (col == pattern_str)
            elif bp.pattern_type == PatternTypeEnum.WILDCARD:
                # Escape SQL wildcards within the pattern before replacing user wildcards
                sql_pattern = pattern_str.replace('%', '\\%').replace('_', '\\_').replace('*', '%')
                filter_expr = col.like(sql_pattern, escape='\\') # Specify escape character
            elif bp.pattern_type == PatternTypeEnum.REGEX:
                # Use regexp_match for PostgreSQL or appropriate function for other DBs
                filter_expr = col.regexp_match(pattern_str) # Assumes PostgreSQL syntax

            if filter_expr is not None:
                if bp.is_exclusion:
                    exclusion_filters.append(filter_expr)
                else:
                    inclusion_filters.append(filter_expr)

        is_excluded_bot = sa.or_(*exclusion_filters) if exclusion_filters else sa.false()
        is_included_bot = sa.or_(*inclusion_filters) if inclusion_filters else sa.false()

        # A commit IS a bot if it matches any exclusion OR any inclusion
        final_bot_condition = sa.or_(is_excluded_bot, is_included_bot)
        return final_bot_condition