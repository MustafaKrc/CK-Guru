# backend/app/api/v1/endpoints/datasets.py
import csv
import io
import logging
from typing import Any, AsyncGenerator, Dict, List

import pandas as pd
import pyarrow.parquet as pq
import s3fs
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.celery_app import backend_celery_app
from shared import schemas
from shared.core.config import settings
from shared.db.models.cleaning_rule_definitions import CleaningRuleDefinitionDB
from shared.db.models.dataset import DatasetStatusEnum
from shared.db_session import get_async_db_session
from shared.schemas import RuleDefinition as BackendRuleDefinitionSchema

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

router = APIRouter()


# --- Endpoint to list available rules ---
@router.get(
    "/datasets/available-cleaning-rules",
    response_model=List[BackendRuleDefinitionSchema],
    summary="Get Available Dataset Cleaning Rules",
    description="Lists the cleaning rules implemented by active workers, read from the database.",
)
async def get_available_cleaning_rules_endpoint(
    db: AsyncSession = Depends(get_async_db_session),
):
    """Returns the list of implemented cleaning rules definitions from the DB."""
    logger.info("Fetching available cleaning rules from database...")
    stmt = (
        select(CleaningRuleDefinitionDB)
        .where(CleaningRuleDefinitionDB.is_implemented)
        .order_by(CleaningRuleDefinitionDB.name)
    )  # Order for consistency

    result = await db.execute(stmt)
    db_rules = result.scalars().all()

    # Convert DB models to Pydantic response models
    # Pydantic should handle the conversion if field names/types match
    response_rules = [
        BackendRuleDefinitionSchema.model_validate(rule) for rule in db_rules
    ]

    logger.info(f"Returning {len(response_rules)} available cleaning rules.")
    return response_rules


@router.post(
    "/repositories/{repo_id}/datasets",
    response_model=schemas.DatasetTaskResponse,  # Return task info
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create and Generate Dataset",
    description="Defines a new dataset configuration and queues a background task to generate it.",
)
async def create_dataset_endpoint(
    repo_id: int,
    dataset_in: schemas.DatasetCreate,
    db: AsyncSession = Depends(get_async_db_session),
):
    """Create a dataset definition and dispatch the generation task."""
    # Check if repository exists
    repo = await crud.crud_repository.get_repository(db, repo_id=repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found"
        )

    # Validate config (Pydantic does this on input, but add custom validation if needed)
    # E.g., check if selected feature columns actually exist or can be derived

    # Create dataset definition in DB with PENDING status
    try:
        db_dataset = await crud.crud_dataset.create_dataset(
            db=db, obj_in=dataset_in, repository_id=repo_id
        )
    except Exception as e:  # Catch potential DB errors during creation
        logger.error(
            f"Failed to create dataset definition in DB for repo {repo_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save dataset definition.",
        )

    # Dispatch Celery task
    task_name = "tasks.generate_dataset"  # Match worker task name
    try:
        task = backend_celery_app.send_task(
            task_name,
            args=[db_dataset.id],  # Pass the dataset ID to the task
            queue="dataset",
        )
        logger.info(
            f"Dispatched task '{task_name}' for dataset ID {db_dataset.id}, task ID: {task.id}"
        )
        return schemas.DatasetTaskResponse(dataset_id=db_dataset.id, task_id=task.id)
    except Exception as e:
        logger.error(
            f"Failed to submit Celery task '{task_name}' for dataset ID {db_dataset.id}: {e}",
            exc_info=True,
        )
        # Attempt to mark the created dataset as failed
        try:
            await crud.crud_dataset.update_dataset_status(
                db,
                dataset_id=db_dataset.id,
                status=DatasetStatusEnum.FAILED,  # Use Enum member
                status_message=f"Failed to queue generation task: {str(e)}",
            )
        except Exception as update_err:
            logger.error(
                f"Failed to mark dataset {db_dataset.id} as failed after queue error: {update_err}"
            )
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
    db: AsyncSession = Depends(get_async_db_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    """Retrieve all datasets defined for a specific repository."""
    # Check if repository exists (optional, protects against invalid repo_id)
    repo = await crud.crud_repository.get_repository(db, repo_id=repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found"
        )

    datasets = await crud.crud_dataset.get_datasets_by_repository(
        db=db, repository_id=repo_id, skip=skip, limit=limit
    )
    return datasets


@router.get(
    "/datasets/{dataset_id}",  # Use path prefix from router include
    response_model=schemas.DatasetRead,
    summary="Get Dataset Details",
    responses={404: {"description": "Dataset not found"}},
)
async def get_dataset_endpoint(
    dataset_id: int,
    db: AsyncSession = Depends(get_async_db_session),
):
    """Retrieve details and status for a specific dataset definition."""
    db_dataset = await crud.crud_dataset.get_dataset(db, dataset_id=dataset_id)
    if db_dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
        )
    return db_dataset


@router.delete(
    "/datasets/{dataset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Dataset Definition and Queue Object Deletion",  # Updated summary
    responses={
        404: {"description": "Dataset definition not found"},
        # Removed 500 for object storage fail, as it's now async
    },
)
async def delete_dataset_endpoint(
    dataset_id: int,
    db: AsyncSession = Depends(get_async_db_session),
):
    """
    Delete a dataset definition from the database and queues a background
    task to delete the corresponding object from storage.
    """
    db_dataset = await crud.crud_dataset.get_dataset(db=db, dataset_id=dataset_id)
    if db_dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset definition not found"
        )

    storage_uri_to_delete = db_dataset.storage_path
    repo_id_log = db_dataset.repository_id

    # Delete DB record first
    deleted_db_record = await crud.crud_dataset.delete_dataset(
        db=db, dataset_id=dataset_id
    )
    if deleted_db_record is None:
        logger.error(
            f"Failed to delete dataset definition {dataset_id} from DB after confirming existence."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete dataset definition from database.",
        )

    logger.info(
        f"Dataset definition {dataset_id} for repository {repo_id_log} deleted from DB."
    )

    # Queue background task for object deletion
    if storage_uri_to_delete and storage_uri_to_delete.startswith("s3://"):
        try:
            task_name = "tasks.delete_storage_object"
            backend_celery_app.send_task(
                task_name,
                args=[storage_uri_to_delete],
                queue="dataset",  # Or a dedicated 'cleanup' queue
            )
            logger.info(
                f"Queued task '{task_name}' to delete object: {storage_uri_to_delete}"
            )
        except Exception as e:
            # Log failure to queue, but don't fail the API request (DB record is gone)
            logger.error(
                f"Failed to queue deletion task for object {storage_uri_to_delete}: {e}",
                exc_info=True,
            )
            # TODO: Implement monitoring/alerting for failed task queuing
    else:
        logger.warning(
            f"Dataset {dataset_id} had no valid storage path '{storage_uri_to_delete}', skipping object deletion task."
        )

    return None  # Return No Content (HTTP 204)


async def get_valid_dataset_uri(dataset_id: int, db: AsyncSession) -> str:
    """Gets dataset, checks status, returns object storage URI, raises HTTPException on error."""
    db_dataset = await crud.crud_dataset.get_dataset(db, dataset_id=dataset_id)
    if db_dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
        )
    if db_dataset.status != DatasetStatusEnum.READY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dataset is not ready. Current status: {db_dataset.status.value}",
        )
    if not db_dataset.storage_path or not db_dataset.storage_path.startswith(
        "s3://"
    ):  # Basic check
        logger.error(
            f"Dataset ID {dataset_id} is READY but has invalid/missing storage path: {db_dataset.storage_path}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dataset is marked ready but its storage path is missing or invalid.",
        )

    logger.debug(f"Accessing dataset object at: {db_dataset.storage_path}")
    # Further validation could involve an `fs.exists(uri)` check here, but adds latency
    return db_dataset.storage_path


@router.get(
    "/datasets/{dataset_id}/view",
    response_model=List[Dict[str, Any]],
    summary="View Dataset Content (Paginated from Object Storage)",
    description="Reads rows from the generated Parquet dataset object with pagination. May be slow for large datasets.",
    # ... (responses remain similar) ...
)
async def view_dataset_content(
    dataset_id: int,
    db: AsyncSession = Depends(get_async_db_session),
    skip: int = Query(0, ge=0, description="Number of rows to skip."),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of rows to return."
    ),
):
    """Reads dataset rows from object storage using PyArrow iteration."""
    object_storage_uri = await get_valid_dataset_uri(dataset_id, db)
    storage_options = settings.s3_storage_options

    rows_collected = []
    try:
        # Use fsspec filesystem object with pyarrow
        fs = s3fs.S3FileSystem(**storage_options)
        # Need to strip s3:// prefix for path argument in pq.ParquetFile with filesystem
        s3_path = object_storage_uri.replace("s3://", "")

        with fs.open(s3_path, "rb") as f:  # Open file handle via fsspec
            parquet_file = pq.ParquetFile(f)
            logger.info(
                f"Total rows in dataset {dataset_id} object: {parquet_file.metadata.num_rows}"
            )

            # --- Pagination Logic (needs careful implementation for streaming) ---
            # Simple approach: Read desired range if possible, or iterate batches
            # Reading specific row groups might be more efficient if skip is large
            # For now, stick to iterating batches and slicing in memory for simplicity:
            total_rows_seen = 0
            for batch in parquet_file.iter_batches(batch_size=65536):
                if not rows_collected and total_rows_seen + batch.num_rows <= skip:
                    total_rows_seen += batch.num_rows
                    continue

                batch_df = batch.to_pandas(types_mapper=pd.ArrowDtype)
                start_index_in_batch = max(0, skip - total_rows_seen)
                rows_needed = limit - len(rows_collected)
                end_index_in_batch = start_index_in_batch + rows_needed
                rows_to_add_df = batch_df.iloc[start_index_in_batch:end_index_in_batch]

                rows_to_add = rows_to_add_df.to_dict(orient="records")
                rows_collected.extend(rows_to_add)
                total_rows_seen += batch.num_rows

                if len(rows_collected) >= limit:
                    break

        logger.info(
            f"Returning {len(rows_collected)} rows for dataset {dataset_id} (skip={skip}, limit={limit})"
        )
        return rows_collected

    except (
        FileNotFoundError
    ):  # If fs.exists failed or object deleted between check and read
        raise HTTPException(
            status_code=404, detail="Dataset object not found in storage."
        )
    except Exception as e:
        logger.error(
            f"Error reading Parquet object {object_storage_uri} for view: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to read dataset content: {e}"
        )


@router.get(
    "/datasets/{dataset_id}/download",
    # response_class=FileResponse, # Changed to StreamingResponse
    summary="Download Generated Dataset as CSV",
    description="Downloads the complete generated dataset by converting the stored Parquet file to CSV format on-the-fly.",
    # ... (responses remain similar, but content type might change slightly) ...
    responses={
        200: {
            "content": {"text/csv": {}},  # Use octet-stream for streaming generally
            "description": "CSV  file download.",
        },
        404: {"description": "Dataset or file not found"},
        409: {"description": "Dataset not ready"},
        500: {"description": "Error accessing dataset file"},
    },
)
async def download_dataset_file_as_csv(
    dataset_id: int,
    db: AsyncSession = Depends(get_async_db_session),
):
    """Streams dataset content as CSV from Parquet stored in object storage."""
    object_storage_uri = await get_valid_dataset_uri(dataset_id, db)
    storage_options = settings.s3_storage_options
    # Define the CSV filename for the download
    csv_filename = f"dataset_{dataset_id}.csv"

    async def generate_csv_chunks() -> AsyncGenerator[bytes, None]:
        """Generator function to read Parquet, convert to CSV chunks, and yield bytes."""
        try:
            logger.info(f"Starting CSV conversion stream for {object_storage_uri}")
            fs = s3fs.S3FileSystem(**storage_options)
            s3_path = object_storage_uri.replace("s3://", "")

            with fs.open(s3_path, "rb") as f:
                parquet_file = pq.ParquetFile(f)
                first_chunk = True
                # Iterate through batches (adjust batch_size based on typical row size and memory)
                for i, batch in enumerate(parquet_file.iter_batches(batch_size=10000)):
                    logger.debug(f"Processing batch {i} for CSV conversion...")
                    batch_df = batch.to_pandas(types_mapper=pd.ArrowDtype)

                    # Use io.StringIO to write CSV chunk to memory buffer
                    output = io.StringIO()
                    batch_df.to_csv(
                        output,
                        header=first_chunk,  # Include header only for the first chunk
                        index=False,  # Do not write pandas index
                        quoting=csv.QUOTE_NONNUMERIC,  # Example: Quote non-numeric fields
                        escapechar="\\",  # Example: Use backslash for escaping
                    )
                    csv_chunk = output.getvalue()
                    output.close()

                    # Yield the CSV chunk encoded as bytes
                    yield csv_chunk.encode("utf-8")

                    if first_chunk:
                        first_chunk = False  # Header written, disable for next chunks

            logger.info(f"Finished CSV conversion stream for {object_storage_uri}")

        except FileNotFoundError:
            logger.error(
                f"Parquet object not found during streaming: {object_storage_uri}"
            )
            # Raising exception inside generator might be tricky for FastAPI, log and yield nothing more.
            # Or find a way to signal error to StreamingResponse. Logging is essential.
            # Let's try raising it to see how FastAPI handles it.
            raise HTTPException(
                status_code=404, detail="Dataset object not found in storage."
            )
        except Exception as e:
            logger.error(
                f"Error during CSV conversion stream for {object_storage_uri}: {e}",
                exc_info=True,
            )
            # Raise HTTP exception to signal failure during streaming
            raise HTTPException(
                status_code=500, detail=f"Failed during CSV conversion stream: {e}"
            )

    # Return a StreamingResponse using the generator
    return StreamingResponse(
        content=generate_csv_chunks(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{csv_filename}"'},
    )
