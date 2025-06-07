# shared/repositories/commit_details_repository.py
import logging
from typing import Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from shared.db.models import CommitDetails, CommitFileDiff
from shared.schemas.enums import CommitIngestionStatusEnum

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class CommitDetailsRepository(BaseRepository[CommitDetails]):
    """Handles synchronous database operations for CommitDetails."""

    def get_by_hash(
        self, repo_id: int, commit_hash: str
    ) -> Optional[CommitDetails]:
        with self._session_scope() as session:
            stmt = (
                select(CommitDetails)
                .options(selectinload(CommitDetails.file_diffs))
                .filter_by(repository_id=repo_id, commit_hash=commit_hash)
            )
            return session.execute(stmt).scalar_one_or_none()

    def create_placeholder(
        self, repo_id: int, commit_hash: str, task_id: str
    ) -> CommitDetails:
        """
        Creates or updates a placeholder record for a commit to be ingested.
        This uses an UPSERT to handle race conditions where another process
        might have just created the placeholder.
        """
        with self._session_scope() as session:
            # Placeholder data. Fill with minimal non-nullable data.
            insert_values = {
                "repository_id": repo_id,
                "commit_hash": commit_hash,
                "author_name": "pending",
                "author_email": "pending",
                "author_date": "1970-01-01T00:00:00Z",
                "committer_name": "pending",
                "committer_email": "pending",
                "committer_date": "1970-01-01T00:00:00Z",
                "message": "Ingestion pending...",
                "parents": {},
                "stats_insertions": 0,
                "stats_deletions": 0,
                "stats_files_changed": 0,
                "ingestion_status": CommitIngestionStatusEnum.PENDING,
                "celery_ingestion_task_id": task_id,
                "status_message": "Ingestion task has been queued.",
            }
            stmt = pg_insert(CommitDetails).values(insert_values)
            
            # If the commit already exists, just update the task_id and reset status.
            update_stmt = stmt.on_conflict_do_update(
                index_elements=["repository_id", "commit_hash"],
                set_={
                    "celery_ingestion_task_id": task_id,
                    "ingestion_status": CommitIngestionStatusEnum.PENDING,
                    "status_message": "Ingestion task has been re-queued.",
                },
            ).returning(CommitDetails)

            result = session.execute(update_stmt).scalar_one()
            session.commit()
            return result
    
    def upsert_from_payload(self, payload: Dict):
        """
        Upserts a single commit's full details and its file diffs atomically.
        """
        with self._session_scope() as session:
            try:
                commit_payload = payload['details']
                diffs_payload = payload['diffs']

                # Use PostgreSQL's ON CONFLICT to either insert or update the commit details.
                stmt = pg_insert(CommitDetails).values(commit_payload)
                update_dict = {
                    col.name: getattr(stmt.excluded, col.name)
                    for col in CommitDetails.__table__.columns
                    if col.name not in ["id", "repository_id", "commit_hash", "created_at"]
                }
                
                final_stmt = stmt.on_conflict_do_update(
                    index_elements=["repository_id", "commit_hash"],
                    set_=update_dict,
                ).returning(CommitDetails.id)

                result = session.execute(final_stmt)
                commit_detail_id = result.scalar_one()
                
                # Atomically replace diffs: delete old, insert new.
                session.execute(delete(CommitFileDiff).where(CommitFileDiff.commit_detail_id == commit_detail_id))
                
                if diffs_payload:
                    for diff in diffs_payload:
                        diff['commit_detail_id'] = commit_detail_id
                    session.bulk_insert_mappings(CommitFileDiff, diffs_payload)
                
                session.commit()
                logger.info(f"Successfully upserted details and diffs for commit_detail_id: {commit_detail_id}")
            except SQLAlchemyError as e:
                logger.error(f"Database error during commit details upsert: {e}", exc_info=True)
                session.rollback()
                raise