# backend/app/api/v1/endpoints/ml_jobs.py
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session as SyncSession

from app import crud
from app.core.celery_app import backend_celery_app
from app.services.inference_service import InferenceService
from app.services.xai_service import XAIService
from shared import schemas
from shared.core.config import settings
from shared.db_session import get_async_db_session
from shared.schemas.enums import (
    DatasetStatusEnum,
    JobStatusEnum,
)

from sqlalchemy.ext.asyncio import AsyncSession
from shared.db_session import get_async_db_session # Ensure using async session for API
from shared.repositories import MLModelTypeDefinitionRepository # Async version if exists, or adapt
from shared.schemas.ml_model_type_definition import AvailableModelTypeResponse # For API response

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

router = APIRouter()

# TODO: Implement proper implementation with repository...
@router.get(
    "/model-types",
    response_model=List[AvailableModelTypeResponse],
    summary="List Available Model Types for Training",
    description="Retrieves a list of all enabled model types that can be used for new training jobs, including their hyperparameter schemas.",
)
async def list_available_model_types(
    db: AsyncSession = Depends(get_async_db_session),
):
    logger.info("API: Fetching available model types.")
    
    def get_types_sync(session: SyncSession):
        repo = MLModelTypeDefinitionRepository(lambda: session)
        db_model_types = repo.get_all_enabled(limit=200)
        # Convert each DB model to response schema properly
        response_list = []
        for mt in db_model_types:
            response_list.append(AvailableModelTypeResponse(
                type_name=mt.type_name.value if hasattr(mt.type_name, 'value') else str(mt.type_name),
                display_name=mt.display_name,
                description=mt.description,
                hyperparameter_schema=mt.hyperparameter_schema
            ))
        return response_list

    try:
        response_data = await db.run_sync(get_types_sync)
        logger.info(f"API: Returning {len(response_data)} available model types.")
        return response_data
    except Exception as e:
        logger.error(f"API: Error fetching model types: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve model types.")


# === Training Jobs ===


@router.post(
    "/train",
    response_model=schemas.TrainingJobSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a Model Training Job",
    description="Creates a training job record and dispatches a background task to train the model.",
)
async def submit_training_job(
    *,
    db: AsyncSession = Depends(get_async_db_session),
    job_in: schemas.TrainingJobCreate,
):
    """
    Submit a new model training job.

    - Validates input configuration.
    - Checks if the specified dataset exists and is ready.
    - Creates a `TrainingJob` record in the database.
    - Dispatches a Celery task to the `ml_queue` for the `ml-worker` to process.
    """
    logger.info(
        f"Received training job submission request for dataset {job_in.dataset_id}"
    )

    # --- Validation ---
    # 1. Check if Dataset exists and is READY
    dataset = await crud.crud_dataset.get_dataset(db, dataset_id=job_in.dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=404, detail=f"Dataset ID {job_in.dataset_id} not found."
        )
    if dataset.status != DatasetStatusEnum.READY:
        raise HTTPException(
            status_code=409, detail=f"Dataset {job_in.dataset_id} not READY."
        )
    if not dataset.storage_path:
        raise HTTPException(
            status_code=409, detail=f"Dataset {job_in.dataset_id} has no storage path."
        )

    # --- Create Job Record ---
    try:
        # CRUD function expects a Pydantic model, Pydantic handles enum serialization
        db_job = await crud.crud_training_job.create_training_job(db=db, obj_in=job_in)
        logger.info(f"Created TrainingJob record with ID: {db_job.id}")
    except Exception as e:
        logger.error(f"Failed to create TrainingJob record: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save training job.")

    # --- Dispatch Celery Task ---
    task_name = "tasks.train_model"  # Must match the name in @shared_task in ml worker
    ml_queue = "ml_queue"  # The queue the ML worker listens to

    try:
        task = backend_celery_app.send_task(task_name, args=[db_job.id], queue=ml_queue)
        logger.info(
            f"Dispatched task '{task_name}' to queue '{ml_queue}' for job ID {db_job.id}, task ID: {task.id}"
        )

        # --- Update Job with Task ID ---
        # Associate the Celery task ID with the job record
        update_data = schemas.TrainingJobUpdate(celery_task_id=task.id)
        await crud.crud_training_job.update_training_job(
            db=db, db_obj=db_job, obj_in=update_data
        )
        await db.commit()  # Commit task ID update
        logger.info(f"Updated job {db_job.id} with Celery task ID {task.id}")

        return schemas.TrainingJobSubmitResponse(
            job_id=db_job.id, celery_task_id=task.id
        )

    except Exception as e:
        logger.error(
            f"Failed to submit Celery task '{task_name}' for job ID {db_job.id}: {e}",
            exc_info=True,
        )
        # Attempt to mark the created job as FAILED
        try:
            fail_update = schemas.TrainingJobUpdate(
                status=JobStatusEnum.FAILED, status_message=f"Failed to queue task: {e}"
            )
            # Fetch fresh object for update if session might be dirty
            db_job_fail = await crud.crud_training_job.get_training_job(db, db_job.id)
            if db_job_fail:
                await crud.crud_training_job.update_training_job(
                    db=db, db_obj=db_job_fail, obj_in=fail_update
                )
                await db.commit()
            else:
                await db.rollback()  # Rollback if fetching failed
        except Exception as update_err:
            logger.error(
                f"Failed to mark training job {db_job.id} as failed: {update_err}"
            )
            await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to submit training task.")


@router.get(
    "/train/{job_id}",
    response_model=schemas.TrainingJobRead,
    summary="Get Training Job Details",
    description="Retrieves the details and status of a specific training job.",
    responses={404: {"description": "Training job not found"}},
)
async def get_training_job_details(
    job_id: int,
    db: AsyncSession = Depends(get_async_db_session),
):
    """Retrieve details for a single training job by its ID."""
    db_job = await crud.crud_training_job.get_training_job(db, job_id=job_id)
    if db_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Training job not found"
        )
    # Note: The CRUD function already eager loads the ml_model relationship
    return db_job


@router.get(
    "/train",
    response_model=schemas.PaginatedTrainingJobRead,
    summary="List Training Jobs",
    description="Retrieves a list of training jobs with optional filters and pagination.",
)
async def list_training_jobs(
    db: AsyncSession = Depends(get_async_db_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    dataset_id: Optional[int] = Query(None, description="Filter by dataset ID"),
    status: Optional[JobStatusEnum] = Query(None, description="Filter by job status"),
    name_filter: Optional[str] = Query(None, alias="nameFilter", description="Filter by job name."),
    sort_by: Optional[str] = Query('created_at', alias="sortBy"),
    sort_dir: Optional[str] = Query('desc', alias="sortDir", pattern="^(asc|desc)$")
):
    items, total = await crud.crud_training_job.get_training_jobs(
        db, skip=skip, limit=limit, dataset_id=dataset_id, status=status,
        name_filter=name_filter, sort_by=sort_by, sort_dir=sort_dir
    )
    return schemas.PaginatedTrainingJobRead(items=items, total=total, skip=skip, limit=limit)


# === ML Models ===


@router.get(
    "/models",
    response_model=schemas.PaginatedMLModelRead,
    summary="List ML Models",
    description="Retrieves a list of registered ML models with filtering and pagination.",
)
async def list_ml_models(
    db: AsyncSession = Depends(get_async_db_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    model_name: Optional[str] = Query(None, alias="nameFilter", description="Filter by logical model name (case-insensitive)."),
    model_type: Optional[str] = Query(None, description="Filter by model type."),
    dataset_id: Optional[int] = Query(None, description="Filter by dataset ID."),
    sort_by: Optional[str] = Query('created_at', alias="sortBy", description="Column to sort by."),
    sort_dir: Optional[str] = Query('desc', alias="sortDir", pattern="^(asc|desc)$")
):
    logger.info(
        f"Listing ML models (Name: {model_name}, Type: {model_type}, Dataset: {dataset_id}, Skip: {skip}, Limit: {limit})"
    )
    items, total = await crud.crud_ml_model.get_ml_models(
        db,
        skip=skip,
        limit=limit,
        model_name=model_name,
        model_type=model_type,
        dataset_id=dataset_id,
        sort_by=sort_by,
        sort_dir=sort_dir
    )
    return schemas.PaginatedMLModelRead(
        items=items, total=total, skip=skip, limit=limit
    )


@router.get(
    "/models/{model_id}",
    response_model=schemas.MLModelRead,
    summary="Get ML Model Details",
    description="Retrieves details for a specific ML model by its unique ID.",
    responses={404: {"description": "ML Model not found"}},
)
async def get_ml_model_details(
    model_id: int,
    db: AsyncSession = Depends(get_async_db_session),
):
    """
    Get details for a specific ML Model by its database ID.
    """
    logger.info(f"Fetching details for ML model ID: {model_id}")
    db_model = await crud.crud_ml_model.get_ml_model(db, model_id=model_id)
    if db_model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ML Model not found"
        )
    return db_model


# TODO: Add DELETE /models/{model_id} endpoint later if needed.
# Remember this would need to potentially trigger artifact deletion via a task.

# === Hyperparameter Search Jobs ===


@router.post(
    "/search",
    response_model=schemas.HPSearchJobSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a Hyperparameter Search Job",
    description=(
        "Creates an HP search job record and dispatches a background task to run Optuna. "
        "Allows continuation of existing studies if specified."
    ),
)
async def submit_hp_search_job(
    *,
    db: AsyncSession = Depends(get_async_db_session),
    job_in: schemas.HPSearchJobCreate,  # Use shared schema
):
    """
    Submit a new hyperparameter search job using Optuna.

    - Validates input configuration including Optuna settings.
    - Checks dataset readiness.
    - Handles creation of new studies or continuation of existing ones based on `continue_if_exists` flag.
    - Creates an `HyperparameterSearchJob` record OR uses existing one if continuing.
    - Dispatches a Celery task to the `ml_queue`.
    """
    logger.info(
        f"Received HP search job submission for study '{job_in.optuna_study_name}', dataset {job_in.dataset_id}"
    )

    # --- Validation ---
    # 1. Check Dataset
    dataset = await crud.crud_dataset.get_dataset(db, dataset_id=job_in.dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=404, detail=f"Dataset ID {job_in.dataset_id} not found."
        )
    if dataset.status != DatasetStatusEnum.READY:
        raise HTTPException(
            status_code=409, detail=f"Dataset {job_in.dataset_id} not READY."
        )
    if not dataset.storage_path:
        raise HTTPException(
            status_code=409, detail=f"Dataset {job_in.dataset_id} has no storage path."
        )

    # 2. Validate HP Space (moved before continue logic for clarity)
    if not job_in.config.hp_space:
        raise HTTPException(status_code=400, detail="hp_space cannot be empty.")

    # 3. Handle 'continue_if_exists' logic
    optuna_config = job_in.config.optuna_config
    study_name = job_in.optuna_study_name
    db_job = None  # Initialize db_job to None

    existing_jobs = await crud.crud_hp_search_job.get_hp_search_jobs(
        db, study_name=study_name
    )

    if existing_jobs and existing_jobs[0]:
        first_job = existing_jobs[0][0]  # Get the most recent one if multiple somehow exist
        if optuna_config.continue_if_exists:
            # Check if dataset matches
            if first_job.dataset_id != job_in.dataset_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Study '{study_name}' exists but uses a different dataset (Existing: {first_job.dataset_id}, Requested: {job_in.dataset_id}). Cannot continue.",
                )

            # Check if model type matches (handle potential dict vs object)
            existing_config = first_job.config
            existing_model_type_str = None
            if isinstance(existing_config, dict):
                existing_model_type_str = existing_config.get("model_type")
            elif hasattr(
                existing_config, "model_type"
            ):  # Check if it's an object-like structure
                existing_model_type_str = getattr(
                    existing_config.model_type, "value", None
                )  # Get enum value if possible

            # Compare the string value of the enum
            if existing_model_type_str != job_in.config.model_type.value:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Study '{study_name}' exists but uses different model type (Existing: {existing_model_type_str}, Requested: {job_in.config.model_type.value}). Cannot continue.",
                )

            logger.info(
                f"Study '{study_name}' exists and matches. Using existing job ID {first_job.id} for continuation."
            )
            db_job = first_job  # Use the existing job object

        else:  # Job exists, but continue_if_exists is False
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Study '{study_name}' already exists. Set 'continue_if_exists: true' in optuna_config to resume, or use a different study name.",
            )
    elif optuna_config.continue_if_exists:
        # continue_if_exists is true, but no job found - proceed to create new
        logger.warning(
            f"Continue requested for study '{study_name}', but no existing job found. Will create a new one."
        )

    # --- Create Job Record (Only if not continuing an existing job) ---
    if db_job is None:  # Only create if we didn't find a valid existing job to continue
        try:
            # Use the CRUD function which accepts the shared schema
            db_job = await crud.crud_hp_search_job.create_hp_search_job(
                db=db, obj_in=job_in
            )
            logger.info(f"Created new HPSearchJob record ID: {db_job.id}")
        except IntegrityError as e:
            await db.rollback()
            logger.error(
                f"DB integrity error creating HP job '{study_name}': {e}", exc_info=True
            )
            # Check if the error is specifically the unique constraint violation
            # This handles race conditions where another request created the job
            # between the initial check and this insert attempt.
            if "uq_hp_search_jobs_optuna_study_name" in str(e).lower() or (
                hasattr(e, "diag")
                and hasattr(e.diag, "constraint_name")
                and e.diag.constraint_name == "ix_hp_search_jobs_optuna_study_name"
            ):  # More robust check if available
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Study name '{study_name}' already exists (detected during creation). Please use a different name or set 'continue_if_exists: true'.",
                )
            else:  # Other integrity error
                raise HTTPException(
                    status_code=500,
                    detail=f"Database integrity error during job creation: {e}",
                ) from e
        except Exception as e:
            await db.rollback()  # Ensure rollback on any other error during creation
            logger.error(
                f"Failed to create HyperparameterSearchJob record '{study_name}' in DB: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save new HP search job definition.",
            )

    # --- Dispatch Celery Task ---
    # At this point, db_job should hold either the newly created job or the existing one to continue
    if not db_job or not db_job.id:
        # This should ideally not happen if logic above is correct, but as a safeguard:
        logger.error(
            f"Failed to obtain a valid job ID for study '{study_name}' before dispatching task."
        )
        raise HTTPException(
            status_code=500,
            detail="Internal error: Could not determine job ID for task dispatch.",
        )

    task_name = "tasks.hyperparameter_search"  # Must match worker task name
    ml_queue = "ml_queue"

    try:
        task = backend_celery_app.send_task(
            task_name,
            args=[db_job.id],  # Pass the correct HPSearchJob ID (new or existing)
            queue=ml_queue,
        )
        logger.info(
            f"Dispatched task '{task_name}' to queue '{ml_queue}' for job ID {db_job.id}, task ID: {task.id}"
        )

        # --- Update Job with Task ID (even for continued jobs, update with the latest task ID) ---
        update_data = schemas.HPSearchJobUpdate(celery_task_id=task.id)
        # Fetch the job again before update to ensure the session has the latest state,
        # especially important if we used an existing 'first_job' object earlier.
        db_job_to_update = await crud.crud_hp_search_job.get_hp_search_job(
            db, db_job.id
        )
        if not db_job_to_update:
            # Should not happen if we just created or found it, but handle defensively
            logger.error(
                f"Could not re-fetch job ID {db_job.id} before updating task ID."
            )
            await db.rollback()  # Rollback potential creation if we can't update
            raise HTTPException(
                status_code=500, detail="Failed to update job with task ID."
            )

        await crud.crud_hp_search_job.update_hp_search_job(
            db=db, db_obj=db_job_to_update, obj_in=update_data
        )
        await db.commit()  # Commit the task ID update
        logger.info(f"Updated HP job {db_job.id} with Celery task ID {task.id}")
        return schemas.HPSearchJobSubmitResponse(
            job_id=db_job.id, celery_task_id=task.id
        )

    except Exception as e:
        logger.error(
            f"Failed Celery task submit '{task_name}' job={db_job.id}: {e}",
            exc_info=True,
        )
        # Attempt to mark the job as FAILED (whether new or existing)
        try:
            fail_update = schemas.HPSearchJobUpdate(
                status=JobStatusEnum.FAILED, status_message=f"Failed queue task: {e}"
            )
            # Fetch fresh object for update
            db_job_fail = await crud.crud_hp_search_job.get_hp_search_job(db, db_job.id)
            if db_job_fail:
                await crud.crud_hp_search_job.update_hp_search_job(
                    db=db, db_obj=db_job_fail, obj_in=fail_update
                )
                await db.commit()
            else:
                await db.rollback()  # Rollback creation if we can't mark as failed
        except Exception as update_err:
            logger.error(
                f"Failed mark HP job {db_job.id} failed after task dispatch error: {update_err}"
            )
            await db.rollback()  # Rollback any pending changes (like job creation)
        raise HTTPException(status_code=500, detail="Failed submit HP search task.")


@router.get(
    "/search/{job_id}",
    response_model=schemas.HPSearchJobRead,  # Use shared schema
    summary="Get HP Search Job Details",
    description="Retrieves the details, status, and results of a specific HP search job.",
    responses={404: {"description": "HP Search job not found"}},
)
async def get_hp_search_job_details(
    job_id: int,
    db: AsyncSession = Depends(get_async_db_session),
):
    """Retrieve details for a single HP search job by its ID."""
    db_job = await crud.crud_hp_search_job.get_hp_search_job(db, job_id=job_id)
    if db_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="HP Search job not found"
        )
    # CRUD function already handles eager loading of best_ml_model
    return db_job


@router.get(
    "/search",
    response_model=schemas.PaginatedHPSearchJobRead,
    summary="List HP Search Jobs",
    description="Retrieves a list of HP search jobs with optional filters and pagination.",
)
async def list_hp_search_jobs(
    db: AsyncSession = Depends(get_async_db_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    dataset_id: Optional[int] = Query(None, description="Filter by dataset ID"),
    status: Optional[JobStatusEnum] = Query(None, description="Filter by job status"),
    name_filter: Optional[str] = Query(None, alias="nameFilter", description="Filter by Optuna study name."),
    sort_by: Optional[str] = Query('created_at', alias="sortBy"),
    sort_dir: Optional[str] = Query('desc', alias="sortDir", pattern="^(asc|desc)$")
):
    items, total = await crud.crud_hp_search_job.get_hp_search_jobs(
        db, skip=skip, limit=limit, dataset_id=dataset_id, status=status,
        name_filter=name_filter, sort_by=sort_by, sort_dir=sort_dir
    )
    return schemas.PaginatedHPSearchJobRead(items=items, total=total, skip=skip, limit=limit)


# === Manual Inference Trigger ===


@router.post(
    "/infer/manual",
    response_model=schemas.InferenceTriggerResponse,  # Use shared schema
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Inference for a Specific Commit",
    description="Manually triggers the feature extraction and inference pipeline for a given commit hash.",
)
async def trigger_manual_inference(
    request_body: schemas.ManualInferenceRequest,  # Use the new request schema
    inference_service: InferenceService = Depends(InferenceService),  # Inject service
):
    """
    Initiates the inference process for a specified repository commit using the InferenceService.
    """
    logger.info(f"API: Received manual inference request: {request_body}")
    # Service handles validation, DB creation, and task dispatch
    job_id, task_id = await inference_service.trigger_inference(
        repo_id=request_body.repo_id,
        commit_hash=request_body.target_commit_hash,
        model_id=request_body.ml_model_id,
        trigger_source="manual",
    )
    return schemas.InferenceTriggerResponse(
        inference_job_id=job_id,
        initial_task_id=task_id,  # This is now the feature extraction task ID
    )


@router.get(
    "/infer/{job_id}",
    response_model=schemas.InferenceJobRead,
    summary="Get Inference Job Details",
    description="Retrieves the details, status, and potentially the prediction result of a specific inference job.",
    responses={404: {"description": "Inference job not found"}},
)
async def get_inference_job_details(
    job_id: int,
    inference_service: InferenceService = Depends(InferenceService),  # Inject service
):
    """Retrieve details for a single inference job by its ID using the InferenceService."""
    return await inference_service.get_inference_status(job_id)


@router.get(
    "/infer",
    response_model=schemas.PaginatedInferenceJobRead,
    summary="List Inference Jobs",
    description="Retrieves a list of inference jobs with optional filters and pagination.",
)
async def list_inference_jobs(
    db: AsyncSession = Depends(get_async_db_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    model_id: Optional[int] = Query(None, description="Filter by ML Model ID used."),
    status: Optional[JobStatusEnum] = Query(None, description="Filter by job status"),
    name_filter: Optional[str] = Query(None, alias="nameFilter", description="Filter by commit hash."),
    sort_by: Optional[str] = Query('created_at', alias="sortBy"),
    sort_dir: Optional[str] = Query('desc', alias="sortDir", pattern="^(asc|desc)$")
):
    items, total = await crud.crud_inference_job.get_inference_jobs(
        db, skip=skip, limit=limit, model_id=model_id, status=status,
        name_filter=name_filter, sort_by=sort_by, sort_dir=sort_dir
    )
    return schemas.PaginatedInferenceJobRead(items=items, total=total, skip=skip, limit=limit)


# --- XAI Orchestration ---
@router.post(
    "/infer/{job_id}/explain",
    response_model=schemas.TaskResponse,  # Return orchestrator task info
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger XAI Explanation Generation",
    description="Initiates the background process to generate all applicable XAI explanations for a completed inference job.",
    responses={
        404: {"description": "Inference job not found"},
        409: {"description": "Inference job not in SUCCESS state"},
        500: {"description": "Failed to dispatch XAI orchestration task"},
    },
)
async def trigger_xai_explanations(
    job_id: int, xai_service: XAIService = Depends(XAIService)  # Inject service
):
    """Triggers the XAI orchestration task for a given inference job ID."""
    logger.info(
        f"API: Received request to trigger XAI orchestration for InferenceJob {job_id}"
    )
    orchestration_task_id = await xai_service.trigger_xai_orchestration(job_id)
    return schemas.TaskResponse(
        task_id=orchestration_task_id,
        message="XAI orchestration task submitted successfully.",
    )
