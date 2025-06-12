# backend/app/api/v1/endpoints/bot_patterns.py
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from shared import schemas
from shared.core.config import settings
from shared.db_session import get_async_db_session

logger = logging.getLogger(__name__)

router = APIRouter()

# === Global Bot Patterns ===

@router.post(
    "/bot-patterns",
    response_model=schemas.BotPatternRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Global Bot Pattern",
    tags=["Bot Patterns"],
)
async def create_global_bot_pattern(
    pattern_in: schemas.BotPatternCreate,
    db: AsyncSession = Depends(get_async_db_session),
):
    """Create a new global bot pattern (not tied to a specific repository)."""
    if pattern_in.repository_id is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot set repository_id for a global bot pattern.")
    
    pattern_in.repository_id = None
    db_pattern = await crud.crud_bot_pattern.create_bot_pattern(db=db, obj_in=pattern_in)
    return db_pattern

@router.get(
    "/bot-patterns",
    response_model=schemas.PaginatedBotPatternRead,
    summary="List Global Bot Patterns",
    tags=["Bot Patterns"],
)
async def list_global_bot_patterns(
    db: AsyncSession = Depends(get_async_db_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """Retrieve a list of global bot patterns."""
    patterns, total = await crud.crud_bot_pattern.get_bot_patterns(db=db, repository_id=None, skip=skip, limit=limit)
    return schemas.PaginatedBotPatternRead(items=patterns, total=total)

# === Repository-Specific Bot Patterns ===

@router.post(
    "/repositories/{repo_id}/bot-patterns",
    response_model=schemas.BotPatternRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Repository-Specific Bot Pattern",
    tags=["Bot Patterns", "Repositories"],
)
async def create_repo_bot_pattern(
    repo_id: int,
    pattern_in: schemas.BotPatternCreate,
    db: AsyncSession = Depends(get_async_db_session),
):
    """Create a new bot pattern specifically for a given repository."""
    repo = await crud.crud_repository.get_repository(db, repo_id=repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    
    pattern_in.repository_id = repo_id
    db_pattern = await crud.crud_bot_pattern.create_bot_pattern(db=db, obj_in=pattern_in)
    return db_pattern

@router.get(
    "/repositories/{repo_id}/bot-patterns",
    response_model=schemas.PaginatedBotPatternRead,
    summary="List Bot Patterns for a Repository (includes global)",
    tags=["Bot Patterns", "Repositories"],
)
async def list_repo_bot_patterns(
    repo_id: int,
    include_global: bool = Query(True, description="Include global patterns in the list"),
    db: AsyncSession = Depends(get_async_db_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """Retrieve bot patterns for a specific repository, optionally including global ones."""
    repo = await crud.crud_repository.get_repository(db, repo_id=repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    patterns, total = await crud.crud_bot_pattern.get_bot_patterns(db=db, repository_id=repo_id, include_global=include_global, skip=skip, limit=limit)
    return schemas.PaginatedBotPatternRead(items=patterns, total=total)

# === Operations on Specific Patterns (by ID) ===

@router.get(
    "/bot-patterns/{pattern_id}",
    response_model=schemas.BotPatternRead,
    summary="Get a Specific Bot Pattern by ID",
    tags=["Bot Patterns"],
)
async def get_bot_pattern(
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
    tags=["Bot Patterns"],
)
async def update_bot_pattern(
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
    tags=["Bot Patterns"],
)
async def delete_bot_pattern(
    pattern_id: int,
    db: AsyncSession = Depends(get_async_db_session),
):
    """Delete a bot pattern by its ID."""
    deleted_pattern = await crud.crud_bot_pattern.delete_bot_pattern(db=db, pattern_id=pattern_id)
    if deleted_pattern is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot Pattern not found")
    return None