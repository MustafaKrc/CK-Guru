# shared/repositories/repository_repository.py
import logging
import re
from urllib.parse import urlparse
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .base_repository import BaseRepository
from shared.db.models import Repository
from shared.schemas.repository import RepositoryCreate, RepositoryUpdate

logger = logging.getLogger(__name__)

class RepositoryRepository(BaseRepository[Repository]):
    """Handles synchronous database operations for Repository."""

    def _extract_repo_name(self, git_url: str) -> str:
        """Extracts a plausible repository name from a Git URL."""
        try:
            if ':' in git_url and '@' in git_url.split(':')[0]: path_part = git_url.split(':')[-1]
            else: path_part = urlparse(git_url).path
            cleaned_path = path_part.strip('/').replace('.git', '')
            if not cleaned_path: return "unknown_repo"
            name = cleaned_path.split('/')[-1]
            return name if name else "unknown_repo"
        except Exception: return "unknown_repo"

    def get_by_id(self, db_id: int) -> Optional[Repository]:
        """Gets a repository by its database ID."""
        with self._session_scope() as session:
            return session.get(Repository, db_id)

    def get_by_git_url(self, git_url: str) -> Optional[Repository]:
        """Gets a repository by its Git URL."""
        with self._session_scope() as session:
            stmt = select(Repository).filter(Repository.git_url == git_url)
            return session.execute(stmt).scalar_one_or_none()

    def list_all(self, skip: int = 0, limit: int = 100) -> Sequence[Repository]:
        """Gets multiple repositories with pagination."""
        with self._session_scope() as session:
            stmt = (
                select(Repository)
                .order_by(Repository.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            return session.execute(stmt).scalars().all()

    def create(self, obj_in: RepositoryCreate) -> Repository:
        """Create a new repository."""
        with self._session_scope() as session:
            try:
                repo_name = self._extract_repo_name(str(obj_in.git_url))
                db_obj = Repository(git_url=str(obj_in.git_url), name=repo_name)
                session.add(db_obj)
                session.commit()
                session.refresh(db_obj)
                logger.info(f"Created repository ID {db_obj.id} ('{db_obj.name}')")
                return db_obj
            except SQLAlchemyError as e:
                logger.error(f"RepositoryRepository: DB error creating repository {obj_in.git_url}: {e}", exc_info=True)
                raise
            except Exception as e:
                logger.error(f"RepositoryRepository: Unexpected error creating repository {obj_in.git_url}: {e}", exc_info=True)
                raise

    def update(self, db_obj: Repository, obj_in: RepositoryUpdate) -> Repository:
        """Update an existing repository."""
        with self._session_scope() as session:
            try:
                if db_obj not in session: db_obj = session.merge(db_obj)
                update_data = obj_in.model_dump(exclude_unset=True)
                for field, value in update_data.items():
                    if value is not None: # Avoid setting None explicitly unless intended
                        setattr(db_obj, field, str(value) if field == 'git_url' else value)
                if hasattr(db_obj, 'updated_at'):
                    from datetime import datetime, timezone
                    db_obj.updated_at = datetime.now(timezone.utc)
                session.add(db_obj)
                session.commit()
                session.refresh(db_obj)
                logger.info(f"Updated repository ID {db_obj.id}")
                return db_obj
            except SQLAlchemyError as e:
                logger.error(f"RepositoryRepository: DB error updating repository {db_obj.id}: {e}", exc_info=True)
                raise
            except Exception as e:
                logger.error(f"RepositoryRepository: Unexpected error updating repository {db_obj.id}: {e}", exc_info=True)
                raise

    def delete(self, repo_id: int) -> bool:
        """Delete a repository by ID. Returns True if deleted, False otherwise."""
        with self._session_scope() as session:
            try:
                db_obj = session.get(Repository, repo_id)
                if db_obj:
                    session.delete(db_obj)
                    session.commit()
                    logger.info(f"Deleted repository ID {repo_id}")
                    return True
                else:
                    logger.warning(f"Repository ID {repo_id} not found for deletion.")
                    return False
            except SQLAlchemyError as e:
                logger.error(f"RepositoryRepository: DB error deleting repository {repo_id}: {e}", exc_info=True)
                raise
            except Exception as e:
                logger.error(f"RepositoryRepository: Unexpected error deleting repository {repo_id}: {e}", exc_info=True)
                raise