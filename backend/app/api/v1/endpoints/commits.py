# backend/app/api/v1/endpoints/commits.py
import logging

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.crud_commit_details import list_commits_paginated
from app.services.commit_service import CommitService
from shared.core.config import settings
from shared.db_session import get_async_db_session
from shared.schemas.commit import CommitPageResponse, PaginatedCommitList
from shared.schemas.enums import CommitIngestionStatusEnum
from shared.schemas.task import TaskResponse

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

router = APIRouter()


@router.get(
    "/repositories/{repo_id}/commits",
    response_model=PaginatedCommitList,
    summary="List Commits for a Repository",
)
async def list_commits_endpoint(
    repo_id: int,
    db: AsyncSession = Depends(get_async_db_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
):
    """
    Retrieves a paginated list of commits for a repository.
    This list is sourced from the `commit_guru_metrics` table which is populated
    during the full, initial ingestion process.
    """
    items, total = await list_commits_paginated(
        db, repo_id=repo_id, skip=skip, limit=limit
    )
    return PaginatedCommitList(items=items, total=total, skip=skip, limit=limit)


@router.get(
    "/repositories/{repo_id}/commits/{commit_hash}",
    response_model=CommitPageResponse,
    summary="Get Commit Details and Status",
    responses={
        status.HTTP_202_ACCEPTED: {"description": "Commit ingestion is in progress."}
    },
)
async def get_commit_details_endpoint(
    repo_id: int,
    commit_hash: str,
    response: Response,  # Inject FastAPI Response to modify status code
    service: CommitService = Depends(CommitService),
):
    """
    Retrieves all available data for a specific commit, including its ingestion status,
    detailed metadata, diffs, and any associated inference jobs.

    - If data is not yet ingested, it returns a `NOT_INGESTED` status.
    - If ingestion is in progress, it returns a `202 Accepted` status code
      along with the `task_id`.
    - If ingestion is complete, it returns a `200 OK` with the full data payload.
    """
    page_data = await service.get_commit_page_data(repo_id, commit_hash)
    if page_data.ingestion_status in [
        CommitIngestionStatusEnum.PENDING,
        CommitIngestionStatusEnum.RUNNING,
    ]:
        response.status_code = status.HTTP_202_ACCEPTED
    return page_data


@router.post(
    "/repositories/{repo_id}/commits/{commit_hash}/ingest",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Ingestion for a Commit",
)
async def ingest_commit_details_endpoint(
    repo_id: int, commit_hash: str, service: CommitService = Depends(CommitService)
):
    """
    Triggers the background task to ingest all details, metrics, and features
    for a specific commit and its parent. This is intended to be called by a user
    action (e.g., clicking an "Ingest" button).
    """
    return await service.trigger_ingestion_for_commit(repo_id, commit_hash)
