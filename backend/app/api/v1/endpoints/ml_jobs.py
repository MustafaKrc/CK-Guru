# backend/app/api/v1/endpoints/ml_jobs.py
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.celery_app import backend_celery_app # Celery app for sending tasks

from shared import schemas
from shared.db_session import get_async_db_session
from shared.core.config import settings # If needed for config values
from shared.db.models.dataset import DatasetStatusEnum # For dataset check
from shared.db.models.training_job import JobStatusEnum # For filtering

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

router = APIRouter()

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
    logger.info(f"Received training job submission request for dataset {job_in.dataset_id}")

    # --- Validation ---
    # 1. Check if Dataset exists and is READY
    dataset = await crud.crud_dataset.get_dataset(db, dataset_id=job_in.dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with ID {job_in.dataset_id} not found.",
        )
    if dataset.status != schemas.DatasetStatusEnum.READY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dataset {job_in.dataset_id} is not ready. Current status: {dataset.status.value}",
        )
    if not dataset.storage_path:
         raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dataset {job_in.dataset_id} is ready but has no storage path defined.",
        )

    # 2. Add more config validation if needed (e.g., check model_type support)
    supported_model_types = ["sklearn_randomforest"] # Example - expand this
    if job_in.config.model_type not in supported_model_types:
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST,
             detail=f"Unsupported model_type '{job_in.config.model_type}'. Supported types: {supported_model_types}",
         )

    # --- Create Job Record ---
    try:
        db_job = await crud.crud_training_job.create_training_job(db=db, obj_in=job_in)
        logger.info(f"Created TrainingJob record with ID: {db_job.id}")
    except Exception as e:
        # Catch potential DB errors during job creation
        logger.error(f"Failed to create TrainingJob record in DB: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save training job definition.",
        )

    # --- Dispatch Celery Task ---
    task_name = "tasks.train_model" # Must match the name in @shared_task in ml worker
    ml_queue = "ml_queue"          # The queue the ML worker listens to

    try:
        task = backend_celery_app.send_task(
            task_name,
            args=[db_job.id], # Pass the TrainingJob ID to the task
            queue=ml_queue
        )
        logger.info(f"Dispatched task '{task_name}' to queue '{ml_queue}' for job ID {db_job.id}, task ID: {task.id}")

        # --- Update Job with Task ID ---
        # Associate the Celery task ID with the job record
        update_data = schemas.TrainingJobUpdate(celery_task_id=task.id)
        await crud.crud_training_job.update_training_job(db=db, db_obj=db_job, obj_in=update_data)
        logger.info(f"Updated job {db_job.id} with Celery task ID {task.id}")

        return schemas.TrainingJobSubmitResponse(job_id=db_job.id, celery_task_id=task.id)

    except Exception as e:
        logger.error(f"Failed to submit Celery task '{task_name}' for job ID {db_job.id}: {e}", exc_info=True)
        # Attempt to mark the created job as FAILED
        try:
            fail_update = schemas.TrainingJobUpdate(
                status=JobStatusEnum.FAILED,
                status_message=f"Failed to queue training task: {str(e)[:200]}" # Truncate error
            )
            await crud.crud_training_job.update_training_job(db=db, db_obj=db_job, obj_in=fail_update)
        except Exception as update_err:
            logger.error(f"Failed to mark training job {db_job.id} as failed after queue error: {update_err}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit training task.",
        )

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training job not found")
    # Note: The CRUD function already eager loads the ml_model relationship
    return db_job

@router.get(
    "/train",
    response_model=List[schemas.TrainingJobRead],
    summary="List Training Jobs",
    description="Retrieves a list of training jobs with optional filters and pagination.",
)
async def list_training_jobs(
    db: AsyncSession = Depends(get_async_db_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    dataset_id: Optional[int] = Query(None, description="Filter by dataset ID"),
    status: Optional[JobStatusEnum] = Query(None, description="Filter by job status"),
):
    """Retrieve a list of training jobs."""
    jobs = await crud.crud_training_job.get_training_jobs(
        db, skip=skip, limit=limit, dataset_id=dataset_id, status=status
    )
    return jobs


# === ML Models ===

@router.get(
    "/models",
    response_model=List[schemas.MLModelRead],
    summary="List ML Models",
    description="Retrieves a list of registered ML models with filtering and pagination.",
)
async def list_ml_models(
    db: AsyncSession = Depends(get_async_db_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    model_name: Optional[str] = Query(None, description="Filter by logical model name."),
    model_type: Optional[str] = Query(None, description="Filter by model type (e.g., sklearn_randomforest)."),
):
    """
    Retrieve ML Models registered in the system.
    Allows filtering by name and type.
    """
    logger.info(f"Listing ML models (Name: {model_name}, Type: {model_type}, Skip: {skip}, Limit: {limit})")
    models = await crud.crud_ml_model.get_ml_models(
        db, skip=skip, limit=limit, model_name=model_name, model_type=model_type
    )
    # Pydantic handles the conversion from ORM model to Read schema
    return models

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ML Model not found")
    return db_model

# TODO: Add DELETE /models/{model_id} endpoint later if needed.
# Remember this would need to potentially trigger artifact deletion via a task.

# === Hyperparameter Search Jobs ===

@router.post(
    "/search",
    response_model=schemas.HPSearchJobSubmitResponse, # Use shared schema
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
    job_in: schemas.HPSearchJobCreate, # Use shared schema
):
    """
    Submit a new hyperparameter search job using Optuna.

    - Validates input configuration including Optuna settings.
    - Checks dataset readiness.
    - Handles creation of new studies or continuation of existing ones based on `continue_if_exists` flag.
    - Creates an `HyperparameterSearchJob` record.
    - Dispatches a Celery task to the `ml_queue`.
    """
    logger.info(f"Received HP search job submission for study '{job_in.optuna_study_name}', dataset {job_in.dataset_id}")

    # --- Validation ---
    # 1. Check Dataset
    dataset = await crud.crud_dataset.get_dataset(db, dataset_id=job_in.dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with ID {job_in.dataset_id} not found.",
        )
    if dataset.status != DatasetStatusEnum.READY: # Use Enum from DB model or shared schema
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dataset {job_in.dataset_id} is not ready. Current status: {dataset.status.value}",
        )
    if not dataset.storage_path:
         raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dataset {job_in.dataset_id} is ready but has no storage path.",
        )

    # 2. Check Model Type Support (if applicable, similar to training)
    supported_model_types = ["sklearn_randomforest"] # Example
    if job_in.config.model_type not in supported_model_types:
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST,
             detail=f"Unsupported model_type '{job_in.config.model_type}' for HP search. Supported types: {supported_model_types}",
         )

    # 3. Handle 'continue_if_exists' logic
    optuna_config = job_in.config.optuna_config
    study_name = job_in.optuna_study_name

    existing_jobs = await crud.crud_hp_search_job.get_hp_search_jobs(db, study_name=study_name)

    if existing_jobs:
        if optuna_config.continue_if_exists:
            first_job = existing_jobs[0]
            # Check if dataset matches
            if first_job.dataset_id != job_in.dataset_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Study '{study_name}' exists but uses a different dataset (Existing: {first_job.dataset_id}, Requested: {job_in.dataset_id}). Cannot continue."
                )

            # Check if model type matches (requires parsing config JSON)
            existing_config = first_job.config # This is a dict/JSON
            existing_model_type = None
            if isinstance(existing_config, dict):
                 existing_model_type = existing_config.get('model_type')

            if existing_model_type != job_in.config.model_type:
                 raise HTTPException(
                     status_code=status.HTTP_409_CONFLICT,
                     detail=f"Study '{study_name}' exists but uses a different model type (Existing: {existing_model_type}, Requested: {job_in.config.model_type}). Cannot continue."
                 )

            logger.info(f"Study '{study_name}' exists and matches dataset/model type. Allowing job creation to continue study.")
            # Allow creation to proceed - the worker will use load_if_exists=True
        else:
            # If study exists and continue_if_exists is False, raise conflict
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"HP Search Job with study name '{study_name}' already exists. Set 'continue_if_exists: true' in optuna_config to resume."
            )
    else:
        # Study does not exist
        if optuna_config.continue_if_exists:
            logger.warning(f"Requested to continue study '{study_name}', but no existing study found. Starting a new one.")
            # Proceed to create the new job

    # 4. Validate HP Space config?
    if not job_in.config.hp_space:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="hp_space configuration cannot be empty.")

    # --- Create Job Record ---
    try:
        # Use the CRUD function which accepts the shared schema
        db_job = await crud.crud_hp_search_job.create_hp_search_job(db=db, obj_in=job_in)
        logger.info(f"Created HyperparameterSearchJob record with ID: {db_job.id}")
    except IntegrityError as e: # Catch potential race condition on unique constraint
         await db.rollback() # Rollback the session
         logger.error(f"Database integrity error creating HP search job (likely study name exists despite check): {e}", exc_info=True)
         # Check if the error message specifically mentions the unique constraint
         if "uq_hp_search_jobs_optuna_study_name" in str(e) or "duplicate key value violates unique constraint" in str(e).lower():
              raise HTTPException(
                  status_code=status.HTTP_409_CONFLICT,
                  detail=f"An HP Search Job with the study name '{job_in.optuna_study_name}' already exists (race condition or validation issue)."
              )
         else:
              # Re-raise other integrity errors
              raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database integrity error: {e}") from e
    except Exception as e:
        await db.rollback() # Ensure rollback on any error
        logger.error(f"Failed to create HyperparameterSearchJob record in DB: {e}", exc_info=True)
        # Consider checking for unique constraint violation on study_name if DB enforces it
        # if "UniqueViolation" in str(e): # Basic check, better check DB exception type
        #      raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Study name '{job_in.optuna_study_name}' already exists.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save HP search job definition.",
        )

    # --- Dispatch Celery Task ---
    task_name = "tasks.hyperparameter_search" # Must match worker task name
    ml_queue = "ml_queue"

    try:
        task = backend_celery_app.send_task(
            task_name,
            args=[db_job.id], # Pass the HPSearchJob ID
            queue=ml_queue
        )
        logger.info(f"Dispatched task '{task_name}' to queue '{ml_queue}' for job ID {db_job.id}, task ID: {task.id}")

        # --- Update Job with Task ID ---
        update_data = schemas.HPSearchJobUpdate(celery_task_id=task.id)
        await crud.crud_hp_search_job.update_hp_search_job(db=db, db_obj=db_job, obj_in=update_data)
        await db.commit() # Commit the task ID update
        logger.info(f"Updated HP search job {db_job.id} with Celery task ID {task.id}")

        # Use the shared response schema
        return schemas.HPSearchJobSubmitResponse(job_id=db_job.id, celery_task_id=task.id)

    except Exception as e:
        logger.error(f"Failed to submit Celery task '{task_name}' for job ID {db_job.id}: {e}", exc_info=True)
        # Attempt to mark the created job as FAILED
        try:
            fail_update = schemas.HPSearchJobUpdate(
                status=JobStatusEnum.FAILED,
                status_message=f"Failed to queue HP search task: {str(e)[:200]}"
            )
            # Need to fetch the object again in a new transaction potentially, or pass ID
            db_job_for_fail = await crud.crud_hp_search_job.get_hp_search_job(db, db_job.id)
            if db_job_for_fail:
                 await crud.crud_hp_search_job.update_hp_search_job(db=db, db_obj=db_job_for_fail, obj_in=fail_update)
                 await db.commit()
        except Exception as update_err:
            logger.error(f"Failed to mark HP search job {db_job.id} as failed after queue error: {update_err}")
            await db.rollback() # Rollback status update attempt

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit HP search task.",
        )


@router.get(
    "/search/{job_id}",
    response_model=schemas.HPSearchJobRead, # Use shared schema
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HP Search job not found")
    # CRUD function already handles eager loading of best_ml_model
    return db_job

@router.get(
    "/search",
    response_model=List[schemas.HPSearchJobRead], # Use shared schema
    summary="List HP Search Jobs",
    description="Retrieves a list of HP search jobs with optional filters and pagination.",
)
async def list_hp_search_jobs(
    db: AsyncSession = Depends(get_async_db_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    dataset_id: Optional[int] = Query(None, description="Filter by dataset ID"),
    status: Optional[JobStatusEnum] = Query(None, description="Filter by job status"),
    study_name: Optional[str] = Query(None, description="Filter by Optuna study name"),
):
    """Retrieve a list of HP search jobs."""
    jobs = await crud.crud_hp_search_job.get_hp_search_jobs(
        db, skip=skip, limit=limit, dataset_id=dataset_id, status=status, study_name=study_name
    )
    return jobs

# === Inference Jobs ===

@router.post(
    "/infer",
    response_model=schemas.InferenceJobSubmitResponse, # Use shared schema
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit an Inference Job",
    description="Creates an inference job record and dispatches a background task to generate predictions.",
)
async def submit_inference_job(
    *,
    db: AsyncSession = Depends(get_async_db_session),
    job_in: schemas.InferenceJobCreate, # Use shared schema
):
    """
    Submit a new inference job using a specified ML Model.

    - Validates input (e.g., model existence).
    - Creates an `InferenceJob` record.
    - Dispatches a Celery task to the `ml_queue`.
    """
    logger.info(f"Received inference job submission request for model ID: {job_in.ml_model_id}")

    # --- Validation ---
    # 1. Check if ML Model exists and has an artifact path
    ml_model = await crud.crud_ml_model.get_ml_model(db, model_id=job_in.ml_model_id)
    if not ml_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ML Model with ID {job_in.ml_model_id} not found.",
        )
    if not ml_model.s3_artifact_path:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, # Conflict: Model exists but unusable
            detail=f"ML Model {job_in.ml_model_id} does not have a saved artifact path (s3_artifact_path is null). Cannot use for inference.",
        )

    # 2. Validate input_reference structure (optional, basic check)
    if not isinstance(job_in.input_reference, dict) or not job_in.input_reference:
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST,
             detail="Invalid input_reference format. Must be a non-empty JSON object.",
         )
    # TODO: Add more specific validation based on the agreed `input_reference` structure

    # --- Create Job Record ---
    try:
        # Use the CRUD function which accepts the shared schema
        db_job = await crud.crud_inference_job.create_inference_job(db=db, obj_in=job_in)
        logger.info(f"Created InferenceJob record with ID: {db_job.id}")
    except Exception as e:
        logger.error(f"Failed to create InferenceJob record in DB: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save inference job definition.",
        )

    # --- Dispatch Celery Task ---
    task_name = "tasks.inference" # Must match worker task name
    ml_queue = "ml_queue"

    try:
        task = backend_celery_app.send_task(
            task_name,
            args=[db_job.id], # Pass the InferenceJob ID
            queue=ml_queue
        )
        logger.info(f"Dispatched task '{task_name}' to queue '{ml_queue}' for job ID {db_job.id}, task ID: {task.id}")

        # --- Update Job with Task ID ---
        update_data = schemas.InferenceJobUpdate(celery_task_id=task.id)
        await crud.crud_inference_job.update_inference_job(db=db, db_obj=db_job, obj_in=update_data)
        logger.info(f"Updated inference job {db_job.id} with Celery task ID {task.id}")

        # Use the shared response schema
        return schemas.InferenceJobSubmitResponse(job_id=db_job.id, celery_task_id=task.id)

    except Exception as e:
        logger.error(f"Failed to submit Celery task '{task_name}' for job ID {db_job.id}: {e}", exc_info=True)
        # Attempt to mark the created job as FAILED
        try:
            fail_update = schemas.InferenceJobUpdate(
                status=JobStatusEnum.FAILED,
                status_message=f"Failed to queue inference task: {str(e)[:200]}"
            )
            await crud.crud_inference_job.update_inference_job(db=db, db_obj=db_job, obj_in=fail_update)
        except Exception as update_err:
            logger.error(f"Failed to mark inference job {db_job.id} as failed after queue error: {update_err}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit inference task.",
        )


@router.get(
    "/infer/{job_id}",
    response_model=schemas.InferenceJobRead, # Use shared schema
    summary="Get Inference Job Details",
    description="Retrieves the details, status, and potentially the prediction result of a specific inference job.",
    responses={404: {"description": "Inference job not found"}},
)
async def get_inference_job_details(
    job_id: int,
    db: AsyncSession = Depends(get_async_db_session),
):
    """Retrieve details for a single inference job by its ID."""
    db_job = await crud.crud_inference_job.get_inference_job(db, job_id=job_id)
    if db_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inference job not found")
    # CRUD function can optionally load related ml_model info if needed
    return db_job

@router.get(
    "/infer",
    response_model=List[schemas.InferenceJobRead], # Use shared schema
    summary="List Inference Jobs",
    description="Retrieves a list of inference jobs with optional filters and pagination.",
)
async def list_inference_jobs(
    db: AsyncSession = Depends(get_async_db_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    model_id: Optional[int] = Query(None, description="Filter by ML Model ID used."),
    status: Optional[JobStatusEnum] = Query(None, description="Filter by job status"),
):
    """Retrieve a list of inference jobs."""
    jobs = await crud.crud_inference_job.get_inference_jobs(
        db, skip=skip, limit=limit, model_id=model_id, status=status
    )
    return jobs

# === Generic Job Status (using Celery Task ID) ===
# Note: This relies on the existing /tasks/{task_id} endpoint.
# We might create a specific /ml/jobs/status/{task_id} endpoint later if we
# want to augment the Celery status with more job-specific DB info.

# Example placeholder if needed:
# @router.get("/jobs/status/{celery_task_id}", ...)
# async def get_ml_job_status_by_task_id(...) -> schemas.TaskStatusResponse:
#    # 1. Call the existing task status endpoint function/logic
#    # 2. Optionally, try to find the associated job in DB tables
#    #    (TrainingJob, HPSearchJob, InferenceJob) using celery_task_id
#    # 3. Augment the response with job-specific details (like DB job ID, status)
#    pass