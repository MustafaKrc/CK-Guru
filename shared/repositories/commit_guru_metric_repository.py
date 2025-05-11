# shared/repositories/commit_guru_metric_repository.py
import logging
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from shared.db.models import CommitGuruMetric, GitHubIssue
from shared.db.models.commit_github_issue_association import (
    commit_github_issue_association_table,
)

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class CommitGuruMetricRepository(BaseRepository[CommitGuruMetric]):
    """Handles database operations for CommitGuruMetric."""

    def get_by_id(self, db_id: int) -> Optional[CommitGuruMetric]:
        """Gets a CommitGuruMetric by its database ID."""
        with self._session_scope() as session:
            return session.get(CommitGuruMetric, db_id)

    def get_by_hash(self, repo_id: int, commit_hash: str) -> Optional[CommitGuruMetric]:
        """Gets a CommitGuruMetric by repository ID and commit hash."""
        with self._session_scope() as session:
            stmt = select(CommitGuruMetric).where(
                CommitGuruMetric.repository_id == repo_id,
                CommitGuruMetric.commit_hash == commit_hash,
            )
            return session.execute(stmt).scalar_one_or_none()

    def bulk_upsert(self, commit_metrics: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Performs a bulk UPSERT of CommitGuruMetric data.

        Args:
            commit_metrics: A list of dictionaries, each representing a commit metric record.

        Returns:
            A dictionary mapping commit_hash to its database ID for the upserted records.
        """
        if not commit_metrics:
            return {}

        model_cols: Set[str] = {c.name for c in CommitGuruMetric.__table__.columns}
        for row in commit_metrics:
            for col in model_cols:
                # Use None (or null()) for missing values
                row.setdefault(col, None)
        index_elements = ["repository_id", "commit_hash"]  # Unique constraint fields
        stmt = pg_insert(CommitGuruMetric).values(commit_metrics)

        # Unique key for ON‑CONFLICT
        index_elements = ["repository_id", "commit_hash"]

        # Plain insert statement (no .values() – we’ll pass rows as executemany params)
        insert_stmt = pg_insert(CommitGuruMetric)

        # Columns to update if the row already exists
        update_columns = {
            c.name: getattr(insert_stmt.excluded, c.name)
            for c in CommitGuruMetric.__table__.c
            if c.name not in (*index_elements, "id", "is_buggy", "fixing_commit_hashes")
        }

        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=index_elements, set_=update_columns
        ).returning(CommitGuruMetric.id, CommitGuruMetric.commit_hash)

        db_ids_map: Dict[str, int] = {}

        with self._session_scope() as session:
            try:

                # executemany → each dict can differ safely
                result = session.execute(upsert_stmt, commit_metrics)
                session.commit()

                for row_id, row_hash in result.fetchall():
                    db_ids_map[row_hash] = row_id

                logger.info(
                    f"CommitGuruMetricRepository: Bulk UPSERT processed {len(db_ids_map)} rows."
                )

            except SQLAlchemyError as e:
                logger.error(
                    f"CommitGuruMetricRepository: Database error during bulk UPSERT: {e}",
                    exc_info=True,
                )
                raise  # Re-raise to be handled by caller
            except Exception as e:
                logger.error(
                    f"CommitGuruMetricRepository: Unexpected error during bulk UPSERT: {e}",
                    exc_info=True,
                )
                raise

        return db_ids_map

    def link_issues_to_commit(self, commit_db_id: int, issue_db_ids: List[int]):
        """Links GitHubIssue records to a CommitGuruMetric record using DB IDs."""
        if not issue_db_ids:
            return

        with self._session_scope() as session:
            try:
                # Fetch the commit object
                commit_metric_obj = session.get(CommitGuruMetric, commit_db_id)
                if not commit_metric_obj:
                    logger.error(
                        f"CommitGuruMetricRepository: Cannot link issues, CommitGuruMetric {commit_db_id} not found."
                    )
                    return

                # Fetch issue objects that need linking
                issues_to_link = (
                    session.execute(
                        select(GitHubIssue).where(GitHubIssue.id.in_(issue_db_ids))
                    )
                    .scalars()
                    .all()
                )

                existing_linked_issue_ids = {
                    issue.id for issue in commit_metric_obj.github_issues
                }
                newly_linked_count = 0

                for issue_obj in issues_to_link:
                    if issue_obj.id not in existing_linked_issue_ids:
                        commit_metric_obj.github_issues.append(issue_obj)
                        newly_linked_count += 1

                if newly_linked_count > 0:
                    session.add(
                        commit_metric_obj
                    )  # Add to session to track relationship changes
                    session.commit()
                    logger.info(
                        f"CommitGuruMetricRepository: Linked {newly_linked_count} new issues to commit {commit_db_id}."
                    )
                else:
                    logger.debug(
                        f"CommitGuruMetricRepository: No new issues to link for commit {commit_db_id}."
                    )

            except SQLAlchemyError as e:
                logger.error(
                    f"CommitGuruMetricRepository: Database error linking issues to commit {commit_db_id}: {e}",
                    exc_info=True,
                )
                raise
            except Exception as e:
                logger.error(
                    f"CommitGuruMetricRepository: Unexpected error linking issues to commit {commit_db_id}: {e}",
                    exc_info=True,
                )
                raise

    def update_bug_links(
        self,
        bug_introducing_commit_ids: Set[int],
        fixing_commit_map: Dict[int, List[str]],
    ):
        """Updates the is_buggy flag and fixing_commit_hashes in the database."""
        if not bug_introducing_commit_ids and not fixing_commit_map:
            logger.info("CommitGuruMetricRepository: No bug link updates required.")
            return

        updated_buggy_count = 0
        updated_fixing_count = 0

        with self._session_scope() as session:
            try:
                # Update 'is_buggy' flag
                if bug_introducing_commit_ids:
                    update_buggy_stmt = (
                        update(CommitGuruMetric)
                        .where(
                            CommitGuruMetric.id.in_(list(bug_introducing_commit_ids))
                        )
                        .values(is_buggy=True)
                        .execution_options(synchronize_session=False)
                    )
                    result = session.execute(update_buggy_stmt)
                    updated_buggy_count = result.rowcount
                    logger.info(
                        f"CommitGuruMetricRepository: Updated is_buggy=True for {updated_buggy_count} commits."
                    )

                # Update 'fixing_commit_hashes'
                for buggy_db_id, fixing_hashes in fixing_commit_map.items():
                    try:
                        update_fixing_stmt = (
                            update(CommitGuruMetric)
                            .where(CommitGuruMetric.id == buggy_db_id)
                            .values(
                                fixing_commit_hashes={"hashes": fixing_hashes}
                            )  # Store as JSON object
                            .execution_options(synchronize_session=False)
                        )
                        session.execute(update_fixing_stmt)
                        updated_fixing_count += 1
                    except Exception as ind_update_err:
                        logger.error(
                            f"CommitGuruMetricRepository: Failed updating fixing_commit_hashes for commit ID {buggy_db_id}: {ind_update_err}",
                            exc_info=False,
                        )
                        # Continue with others

                session.commit()
                logger.info(
                    f"CommitGuruMetricRepository: Updated fixing_commit_hashes for {updated_fixing_count} commits."
                )

            except SQLAlchemyError as e:
                logger.error(
                    f"CommitGuruMetricRepository: Database error updating bug links: {e}",
                    exc_info=True,
                )
                raise
            except Exception as e:
                logger.error(
                    f"CommitGuruMetricRepository: Unexpected error updating bug links: {e}",
                    exc_info=True,
                )
                raise

    def get_earliest_linked_issue_timestamp(
        self, commit_metric_id: int
    ) -> Optional[int]:
        """
        Queries the DB for the minimum created_at_timestamp among issues linked to a commit.
        Returns the timestamp as an integer (Unix epoch seconds) or None.
        """
        with self._session_scope() as session:
            try:
                stmt = (
                    select(func.min(GitHubIssue.created_at_timestamp))
                    .select_from(CommitGuruMetric)  # Start from CommitGuruMetric
                    .join(
                        commit_github_issue_association_table,
                        CommitGuruMetric.id
                        == commit_github_issue_association_table.c.commit_guru_metric_id,
                    )
                    .join(
                        GitHubIssue,
                        GitHubIssue.id
                        == commit_github_issue_association_table.c.github_issue_id,
                    )
                    .where(CommitGuruMetric.id == commit_metric_id)
                    .where(
                        GitHubIssue.created_at_timestamp.isnot(None)
                    )  # Ensure we only consider issues with a timestamp
                )
                earliest_ts = session.execute(stmt).scalar_one_or_none()
                # The result might be BigInteger or int, ensure it's standard int if not None
                return int(earliest_ts) if earliest_ts is not None else None
            except SQLAlchemyError as e:
                logger.error(
                    f"CommitGuruMetricRepository: DB error getting earliest issue timestamp for commit {commit_metric_id}: {e}",
                    exc_info=True,
                )
                return None  # Return None on error
            except Exception as e:
                logger.error(
                    f"CommitGuruMetricRepository: Unexpected error getting earliest issue timestamp for commit {commit_metric_id}: {e}",
                    exc_info=True,
                )
                return None
