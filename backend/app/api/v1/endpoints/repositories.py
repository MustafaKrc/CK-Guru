from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Sequence
import logging

from app import schemas # Use schemas module directly
from app import crud    # Use crud module directly
from app.api import deps

from app.core.celery_app import backend_celery_app

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post(
    "/",
    response_model=schemas.RepositoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new repository entry",
    description="Adds a new repository URL to the system for tracking.",
)
async def create_repository_endpoint(
    *,
    db: AsyncSession = Depends(deps.get_db_session),
    repo_in: schemas.RepositoryCreate,
):
    """
    Create a new repository record in the database.
    """
    existing_repo = await crud.crud_repository.get_repository_by_git_url(db, git_url=str(repo_in.git_url))
    if existing_repo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Repository with Git URL '{repo_in.git_url}' already exists.",
        )
    repository = await crud.crud_repository.create_repository(db=db, obj_in=repo_in)
    return repository


@router.get(
    "/",
    response_model=List[schemas.RepositoryRead], # Return a list
    summary="List registered repositories",
    description="Retrieves a list of repositories with pagination.",
)
async def read_repositories_endpoint(
    db: AsyncSession = Depends(deps.get_db_session),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(100, ge=1, le=200, description="Maximum number of records to return"),
):
    """
    Retrieve repositories.
    """
    repositories: Sequence[schemas.RepositoryRead] = await crud.crud_repository.get_repositories(db, skip=skip, limit=limit)
    # Pydantic V2 automatically handles conversion from ORM model to schema
    # if ConfigDict(from_attributes=True) is set in the schema.
    # No explicit loop needed unless custom mapping is required.
    return repositories


@router.get(
    "/{repo_id}",
    response_model=schemas.RepositoryRead,
    summary="Get a specific repository by ID",
    description="Retrieves details for a single repository.",
    responses={404: {"description": "Repository not found"}}, # Document potential errors
)
async def read_repository_endpoint(
    repo_id: int,
    db: AsyncSession = Depends(deps.get_db_session),
):
    """
    Get repository by ID.
    """
    db_repo = await crud.crud_repository.get_repository(db, repo_id=repo_id)
    if db_repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return db_repo

# Add Update and Delete endpoints later if needed
@router.put(
    "/{repo_id}",
    response_model=schemas.RepositoryRead,
    summary="Update a repository",
    description="Updates an existing repository's information.",
    responses={404: {"description": "Repository not found"}},
)
async def update_repository_endpoint(
    repo_id: int,
    repo_in: schemas.RepositoryUpdate,
    db: AsyncSession = Depends(deps.get_db_session),
):
    """
    Update a repository's details.
    """
    db_repo = await crud.crud_repository.get_repository(db, repo_id=repo_id)
    if db_repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    
    repository = await crud.crud_repository.update_repository(db=db, db_obj=db_repo, obj_in=repo_in)
    return repository


@router.delete(
    "/{repo_id}",
    response_model=schemas.RepositoryRead,
    summary="Delete a repository",
    description="Removes a repository from the system.",
    responses={404: {"description": "Repository not found"}},
)
async def delete_repository_endpoint(
    repo_id: int,
    db: AsyncSession = Depends(deps.get_db_session),
):
    """
    Delete a repository.
    """
    db_repo = await crud.crud_repository.delete_repository(db, repo_id=repo_id)
    if db_repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return db_repo

@router.post(
    "/{repo_id}/ingest",
    response_model=schemas.TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    # ... (rest of definition) ...
)
async def trigger_ingest_task(
    repo_id: int,
    db: AsyncSession = Depends(deps.get_db_session),
):
    """
    Submits a Celery task to create a dataset for the specified repository.
    """
    db_repo = await crud.crud_repository.get_repository(db, repo_id=repo_id)
    if db_repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    # Define the registered name of the task in the worker
    # This MUST match the 'name' argument in @shared_task in the worker code
    task_name = "tasks.ingest_repository"

    try:
        # Send the task using send_task("task_name", args=[...], kwargs={...})
        task = backend_celery_app.send_task(
            task_name,
            args=[db_repo.id, str(db_repo.git_url)], # Positional arguments
            # kwargs={'repo_id': db_repo.id, 'git_url': str(db_repo.git_url)} # Alternatively, use keyword arguments
        )
        logger.info(f"Dispatched task '{task_name}' for repo ID {repo_id}, task ID: {task.id}")

        # Optional: Update repository status in DB here if desired

        return schemas.TaskResponse(task_id=task.id, message="Repository ingestion task submitted.")

    except Exception as e:
        logger.error(f"Failed to submit Celery task '{task_name}' for repo ID {repo_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit background task. Please try again later.",
        )