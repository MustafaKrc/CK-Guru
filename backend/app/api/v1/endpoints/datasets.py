# backend/app/api/v1/endpoints/datasets.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app import schemas, crud
from app.api import deps
from app.core.celery_app import backend_celery_app
from shared.db.models.dataset import DatasetStatusEnum # Import Enum
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# --- Endpoint to list available rules ---
@router.get(
    "/datasets/available-cleaning-rules", # Moved path prefix to router include
    response_model=List[schemas.RuleDefinition],
    summary="Get Available Dataset Cleaning Rules",
    description="Lists the cleaning rules that can be configured during dataset creation."
)
async def get_available_cleaning_rules():
    # (Keep the same implementation returning the list of RuleDefinition schemas as before)
    return [
        schemas.RuleDefinition(name="rule0_drop_duplicates", description="Remove exact duplicate rows.", parameters=[]),
        schemas.RuleDefinition(name="rule2_remove_recent_clean_last_change", description="Exclude clean changes if they are the last change for a class and occurred recently relative to the project's end.", parameters=[schemas.RuleParamDefinition(name="gap_seconds", type="integer", description="Time threshold in seconds.", default=2419200)]), # 4 weeks default
        schemas.RuleDefinition(name="rule3_remove_empty_class", description="Exclude changes resulting in classes with no local methods or fields.", parameters=[]),
        schemas.RuleDefinition(name="rule4_remove_trivial_getset", description="Exclude changes involving only likely getter/setter methods (low WMC/RFC heuristic).", parameters=[]),
        schemas.RuleDefinition(name="rule5_remove_no_added_lines", description="Exclude changes where no lines were added (la == 0).", parameters=[]),
        schemas.RuleDefinition(name="rule6_remove_comment_only_change", description="Exclude changes where likely only comments changed (all d_* metrics are 0).", parameters=[]),
        schemas.RuleDefinition(name="rule7_remove_trivial_method_change", description="Exclude changes with minimal line alterations but changes in method counts.", parameters=[schemas.RuleParamDefinition(name="min_line_change", type="integer", description="Minimum lines added+deleted to be considered non-trivial.", default=10)]),
        schemas.RuleDefinition(name="rule8_remove_type_exception_files", description="Exclude changes to files named like '*Type.java' or '*Exception.java'.", parameters=[]),
        schemas.RuleDefinition(name="rule9_remove_dead_code", description="Exclude changes where the resulting class seems unused (CBO=0 and Fan-in=0 heuristic).", parameters=[]),
        schemas.RuleDefinition(name="rule10_remove_data_class", description="Exclude changes likely representing simple data classes (low WMC/RFC, non-zero fields).", parameters=[]),
        schemas.RuleDefinition(name="rule11_remove_no_code_change", description="Exclude changes where no lines were added or deleted (la == 0 and ld == 0).", parameters=[]),
        schemas.RuleDefinition(name="rule14_filter_large_commits", description="Exclude rows from commits that changed more than N files (applied before clustering).", parameters=[schemas.RuleParamDefinition(name="max_files_changed", type="integer", description="Maximum number of files changed in a commit for its rows to be included.", default=10)]),
        schemas.RuleDefinition(name="rule_cluster_large_commits", description="Cluster rows within commits changing > N files, reducing rows via aggregation.", parameters=[schemas.RuleParamDefinition(name="threshold", type="integer", description="File count threshold to trigger clustering.", default=10)]),
    ]

@router.post(
    "/repositories/{repo_id}/datasets",
    response_model=schemas.DatasetTaskResponse, # Return task info
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create and Generate Dataset",
    description="Defines a new dataset configuration and queues a background task to generate it."
)
async def create_dataset_endpoint(
    repo_id: int,
    dataset_in: schemas.DatasetCreate,
    db: AsyncSession = Depends(deps.get_db_session),
):
    """Create a dataset definition and dispatch the generation task."""
    # Check if repository exists
    repo = await crud.crud_repository.get_repository(db, repo_id=repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    # Validate config (Pydantic does this on input, but add custom validation if needed)
    # E.g., check if selected feature columns actually exist or can be derived

    # Create dataset definition in DB with PENDING status
    try:
        db_dataset = await crud.crud_dataset.create_dataset(db=db, obj_in=dataset_in, repository_id=repo_id)
    except Exception as e: # Catch potential DB errors during creation
        logger.error(f"Failed to create dataset definition in DB for repo {repo_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save dataset definition.")

    # Dispatch Celery task
    task_name = "tasks.generate_dataset" # Match worker task name
    try:
        task = backend_celery_app.send_task(
            task_name,
            args=[db_dataset.id], # Pass the dataset ID to the task
        )
        logger.info(f"Dispatched task '{task_name}' for dataset ID {db_dataset.id}, task ID: {task.id}")
        return schemas.DatasetTaskResponse(dataset_id=db_dataset.id, task_id=task.id)
    except Exception as e:
        logger.error(f"Failed to submit Celery task '{task_name}' for dataset ID {db_dataset.id}: {e}", exc_info=True)
        # Attempt to mark the created dataset as failed
        try:
            await crud.crud_dataset.update_dataset_status(
                db,
                dataset_id=db_dataset.id,
                status=DatasetStatusEnum.FAILED, # Use Enum member
                status_message=f"Failed to queue generation task: {str(e)}"
            )
        except Exception as update_err:
            logger.error(f"Failed to mark dataset {db_dataset.id} as failed after queue error: {update_err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit dataset generation task.",
        )

@router.get(
    "/repositories/{repo_id}/datasets",
    response_model=List[schemas.DatasetRead],
    summary="List Datasets for a Repository",
)
async def list_repository_datasets_endpoint(
    repo_id: int,
    db: AsyncSession = Depends(deps.get_db_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    """Retrieve all datasets defined for a specific repository."""
     # Check if repository exists (optional, protects against invalid repo_id)
    repo = await crud.crud_repository.get_repository(db, repo_id=repo_id)
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    datasets = await crud.crud_dataset.get_datasets_by_repository(
        db=db, repository_id=repo_id, skip=skip, limit=limit
    )
    return datasets

@router.get(
    "/datasets/{dataset_id}", # Use path prefix from router include
    response_model=schemas.DatasetRead,
    summary="Get Dataset Details",
    responses={404: {"description": "Dataset not found"}},
)
async def get_dataset_endpoint(
    dataset_id: int,
    db: AsyncSession = Depends(deps.get_db_session),
):
    """Retrieve details and status for a specific dataset definition."""
    db_dataset = await crud.crud_dataset.get_dataset(db, dataset_id=dataset_id)
    if db_dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    return db_dataset

@router.delete(
    "/datasets/{dataset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Dataset Definition",
    responses={404: {"description": "Dataset not found"}},
)
async def delete_dataset_endpoint(
    dataset_id: int,
    db: AsyncSession = Depends(deps.get_db_session),
):
    """
    Delete a dataset definition from the database.
    Note: This does NOT automatically delete the generated dataset file from storage.
    """
    # TODO: Implement file deletion logic if required (e.g., dispatch another task)
    deleted_dataset = await crud.crud_dataset.delete_dataset(db=db, dataset_id=dataset_id)
    if deleted_dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    logger.info(f"Dataset definition {dataset_id} deleted. Associated file at {deleted_dataset.storage_path} may still exist.")
    return None