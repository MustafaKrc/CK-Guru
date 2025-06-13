# shared/schemas/inference_job.py
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from shared.schemas.enums import JobStatusEnum
from shared.schemas.xai import FilePredictionDetail
from shared.schemas.ml_model import MLModelRead 


# --- Result package stored in InferenceJob ---
class InferenceResultPackage(BaseModel):
    """Structured result stored in the prediction_result field of InferenceJob."""

    commit_prediction: int = Field(
        ...,
        description="Aggregated prediction label for the entire commit (0 or 1, -1 for error).",
    )
    max_bug_probability: float = Field(
        ...,
        description="Maximum probability of being defect-prone found among analyzed instances (-1.0 for error).",
    )
    num_files_analyzed: int = Field(
        ..., description="Number of file/class instances analyzed within the commit."
    )
    # List of prediction details for each analyzed file/class instance
    details: Optional[List[FilePredictionDetail]] = Field(
        None, description="Detailed predictions per file/class."
    )
    # Error message if prediction failed at the handler level
    error: Optional[str] = Field(
        None, description="Error message if prediction failed."
    )

    model_config = ConfigDict(extra="ignore")  # Ignore extra fields if any


class InferenceJobBase(BaseModel):
    ml_model_id: int = Field(
        ..., description="ID of the ML model to use for inference."
    )
    input_reference: Dict[str, Any] = Field(
        ...,
        description="Reference to input data (e.g., {'commit_hash': '...', 'repo_id': ..., 'trigger_source': 'manual'|'webhook'}).",
    )


# --- Create (Internal use) ---
class InferenceJobCreateInternal(InferenceJobBase):
    status: JobStatusEnum = JobStatusEnum.PENDING
    celery_task_id: Optional[str] = None


# --- Update (Internal use) ---
class InferenceJobUpdate(BaseModel):
    celery_task_id: Optional[str] = None
    status: Optional[JobStatusEnum] = None
    status_message: Optional[str] = None
    # Use the result package schema here for validation on update
    prediction_result: Optional[InferenceResultPackage] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(extra="ignore")


# --- Read (API Response) ---
class InferenceJobRead(InferenceJobBase):
    id: int
    celery_task_id: Optional[str] = None
    status: JobStatusEnum
    status_message: Optional[str] = None
    # Use the result package schema here for consistent response structure
    prediction_result: Optional[InferenceResultPackage] = None
    ml_model: Optional[MLModelRead] = None 
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


# --- API Response for Job Submission (Feature Extraction Task) ---
class InferenceTriggerResponse(BaseModel):
    inference_job_id: int = Field(
        ..., description="The ID of the created InferenceJob record."
    )
    initial_task_id: str = Field(
        ..., description="The Celery task ID for the initial feature extraction step."
    )


class PaginatedInferenceJobRead(BaseModel):
    """Response for paginated inference job queries."""

    total: int = Field(..., description="Total number of inference jobs.")
    items: List[InferenceJobRead] = Field(
        ..., description="List of inference jobs in the current page."
    )
    skip: Optional[int] = Field(
        None, description="Number of jobs skipped in the current page."
    )
    limit: Optional[int] = Field(
        None, description="Number of jobs returned in the current page."
    )
