# backend/app/crud/crud_commit_details.py
import logging
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.db.models.commit_details import CommitDetails
from shared.schemas.commit import CommitListItem
from shared.schemas.enums import CommitIngestionStatusEnum

logger = logging.getLogger(__name__)


async def get_by_hash(
    db: AsyncSession, repo_id: int, commit_hash: str
) -> Optional[CommitDetails]:
    """Get a single commit's details by repository and hash, with diffs."""
    stmt = (
        select(CommitDetails)
        .options(selectinload(CommitDetails.file_diffs))
        .filter_by(repository_id=repo_id, commit_hash=commit_hash)
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_by_id(db: AsyncSession, detail_id: int) -> Optional[CommitDetails]:
    """Get a single commit's details by its primary key."""
    result = await db.execute(select(CommitDetails).filter_by(id=detail_id))
    return result.scalars().first()


async def create_placeholder(
    db: AsyncSession, repo_id: int, commit_hash: str
) -> CommitDetails:
    """Creates a placeholder CommitDetails record."""
    from datetime import datetime, timezone

    # Create a new placeholder record
    placeholder = CommitDetails(
        repository_id=repo_id,
        commit_hash=commit_hash,
        ingestion_status=CommitIngestionStatusEnum.PENDING,
        # Fill required fields with placeholder data
        author_name="pending",
        author_email="pending",
        author_date=datetime.fromtimestamp(0, tz=timezone.utc),
        committer_name="pending",
        committer_email="pending",
        committer_date=datetime.fromtimestamp(0, tz=timezone.utc),
        message="Ingestion pending...",
        parents={},
        stats_insertions=0,
        stats_deletions=0,
        stats_files_changed=0,
    )
    db.add(placeholder)
    await db.commit()
    await db.refresh(placeholder)
    logger.info(
        f"Created placeholder CommitDetails record for repo {repo_id}, commit {commit_hash[:7]}"
    )
    return placeholder


async def set_ingestion_task(
    db: AsyncSession, detail_id: int, task_id: str
) -> Optional[CommitDetails]:
    """Updates a CommitDetails record with a new task_id and resets status to PENDING."""
    db_obj = await get_by_id(db, detail_id)
    if not db_obj:
        return None
    
    db_obj.celery_ingestion_task_id = task_id
    db_obj.ingestion_status = CommitIngestionStatusEnum.PENDING
    db_obj.status_message = "Ingestion task has been queued."
    
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def list_commits_paginated(
    db: AsyncSession, repo_id: int, skip: int = 0, limit: int = 100
) -> Tuple[List[CommitListItem], int]:
    """
    Retrieves a paginated list of commits for a repository.
    This queries CommitGuruMetric as it's the most comprehensive list from full ingestion.
    """
    from shared.db.models.commit_guru_metric import CommitGuruMetric

    # Query for the total count first
    count_stmt = select(func.count(CommitGuruMetric.id)).filter_by(repository_id=repo_id)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one_or_none() or 0

    if total == 0:
        return [], 0
    
    # Query for the paginated items
    # LEFT JOIN with commit_details to get the ingestion status
    stmt = (
        select(
            CommitGuruMetric.commit_hash,
            CommitGuruMetric.author_name,
            CommitGuruMetric.author_date,
            CommitGuruMetric.commit_message,
            CommitDetails.ingestion_status,
        )
        .join(
            CommitDetails,
            (CommitGuruMetric.repository_id == CommitDetails.repository_id)
            & (CommitGuruMetric.commit_hash == CommitDetails.commit_hash),
            isouter=True, # LEFT JOIN
        )
        .filter(CommitGuruMetric.repository_id == repo_id)
        .order_by(CommitGuruMetric.author_date_unix_timestamp.desc())
        .offset(skip)
        .limit(limit)
    )
    
    results = await db.execute(stmt)
    items = []
    for row in results.mappings().all():
        items.append(
            CommitListItem(
                commit_hash=row.commit_hash,
                author_name=row.author_name,
                author_date=row.author_date, # Assuming author_date is datetime
                message_short=row.commit_message.split('\n', 1)[0],
                ingestion_status=row.ingestion_status or CommitIngestionStatusEnum.NOT_INGESTED
            )
        )
    
    return items, total