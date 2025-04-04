# backend/app/api/v1/endpoints/bot_patterns.py
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas, crud

from shared.core.config import settings
from shared.db_session import get_async_db_session 

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

router = APIRouter()

# === Global Bot Patterns ===

@router.post(
    "/bot-patterns/", # Route for global patterns
    response_model=schemas.BotPatternRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Global Bot Pattern",
)
async def create_global_bot_pattern_endpoint(
    pattern_in: schemas.BotPatternCreate,
    db: AsyncSession = Depends(get_async_db_session),
):
    """Create a new global bot pattern (not tied to a specific repository)."""
    if pattern_in.repository_id is not None:
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST,
             detail="Cannot set repository_id for a global bot pattern.",
         )
    # Ensure repository_id is explicitly None for creation
    pattern_in.repository_id = None
    # Check for duplicates (optional, handled by DB constraint mostly)
    # ... duplicate check logic if needed ...
    db_pattern = await crud.crud_bot_pattern.create_bot_pattern(db=db, obj_in=pattern_in)
    return db_pattern

@router.get(
    "/bot-patterns/", # Route for global patterns
    response_model=List[schemas.BotPatternRead],
    summary="List Global Bot Patterns",
)
async def read_global_bot_patterns_endpoint(
    db: AsyncSession = Depends(get_async_db_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    """Retrieve a list of global bot patterns."""
    patterns = await crud.crud_bot_pattern.get_bot_patterns(
        db=db, repository_id=None, include_global=True, skip=skip, limit=limit
    )
    return patterns

# === Repository-Specific Bot Patterns ===

@router.post(
    "/repositories/{repo_id}/bot-patterns",
    response_model=schemas.BotPatternRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Repository-Specific Bot Pattern",
)
async def create_repo_bot_pattern_endpoint(
    repo_id: int,
    pattern_in: schemas.BotPatternCreate,
    db: AsyncSession = Depends(get_async_db_session),
):
    """Create a new bot pattern specifically for a given repository."""
     # Check if repository exists
    repo = await crud.crud_repository.get_repository(db, repo_id=repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    # Override or set the repository_id from the path
    pattern_in.repository_id = repo_id
    # ... duplicate check logic if needed ...
    db_pattern = await crud.crud_bot_pattern.create_bot_pattern(db=db, obj_in=pattern_in)
    return db_pattern

@router.get(
    "/repositories/{repo_id}/bot-patterns",
    response_model=List[schemas.BotPatternRead],
    summary="List Bot Patterns for a Repository (includes global)",
)
async def read_repo_bot_patterns_endpoint(
    repo_id: int,
    include_global: bool = Query(True, description="Include global patterns in the list"),
    db: AsyncSession = Depends(get_async_db_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    """Retrieve bot patterns for a specific repository, optionally including global ones."""
     # Check if repository exists (optional, crud function might handle implicitly)
    repo = await crud.crud_repository.get_repository(db, repo_id=repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    patterns = await crud.crud_bot_pattern.get_bot_patterns(
        db=db, repository_id=repo_id, include_global=include_global, skip=skip, limit=limit
    )
    return patterns


# === Operations on Specific Patterns (by ID) ===

@router.get(
    "/bot-patterns/{pattern_id}", # Use a consistent path prefix
    response_model=schemas.BotPatternRead,
    summary="Get a Specific Bot Pattern by ID",
    responses={404: {"description": "Bot Pattern not found"}},
)
async def read_bot_pattern_endpoint(
    pattern_id: int,
    db: AsyncSession = Depends(get_async_db_session),
):
    """Retrieve details for a single bot pattern by its ID."""
    db_pattern = await crud.crud_bot_pattern.get_bot_pattern(db, pattern_id=pattern_id)
    if db_pattern is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot Pattern not found")
    return db_pattern

@router.put(
    "/bot-patterns/{pattern_id}",
    response_model=schemas.BotPatternRead,
    summary="Update a Bot Pattern",
    responses={404: {"description": "Bot Pattern not found"}},
)
async def update_bot_pattern_endpoint(
    pattern_id: int,
    pattern_in: schemas.BotPatternUpdate,
    db: AsyncSession = Depends(get_async_db_session),
):
    """Update an existing bot pattern."""
    db_pattern = await crud.crud_bot_pattern.get_bot_pattern(db, pattern_id=pattern_id)
    if db_pattern is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot Pattern not found")
    updated_pattern = await crud.crud_bot_pattern.update_bot_pattern(db=db, db_obj=db_pattern, obj_in=pattern_in)
    return updated_pattern

@router.delete(
    "/bot-patterns/{pattern_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Bot Pattern",
    responses={404: {"description": "Bot Pattern not found"}},
)
async def delete_bot_pattern_endpoint(
    pattern_id: int,
    db: AsyncSession = Depends(get_async_db_session),
):
    """Delete a bot pattern by its ID."""
    deleted_pattern = await crud.crud_bot_pattern.delete_bot_pattern(db=db, pattern_id=pattern_id)
    if deleted_pattern is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot Pattern not found")
    return None # Return No Content on successful deletion