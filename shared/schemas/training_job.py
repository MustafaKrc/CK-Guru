# shared/schemas/training_job.py
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from shared.schemas.enums import JobStatusEnum, ModelTypeEnum  # Import ModelTypeEnum

from .ml_model import MLModelRead  # To show nested model info


# --- Training Run Config (More specific than raw JSON) ---
class TrainingRunConfig(BaseModel):
    """Configuration for a specific training run."""
    model_name: str = Field(
        ..., description="Base name for the MLModelDB record (e.g., 'MyDataset_RF')"
    )
    model_type: ModelTypeEnum = Field(
        ..., description="Type/architecture of the model (e.g., sklearn_randomforest)."
    )  # Use ModelTypeEnum
    hyperparameters: Dict[str, Any] = Field(
        default_factory=dict, description="Specific hyperparameters to use."
    )

    feature_columns: List[str] = Field(
        ..., description="List of features to use from the dataset."
    )
    target_column: str = Field(..., description="Name of the target column.")
    # -------------------
    # Add evaluation strategy, seed, etc. as needed
    random_seed: Optional[int] = Field(
        42, description="Random seed for reproducibility."
    )
    eval_test_split_size: Optional[float] = Field(
        0.2, ge=0, lt=1, description="Fraction for test split during evaluation."
    )


# --- Base ---
class TrainingJobBase(BaseModel):
    dataset_id: int = Field(..., description="ID of the dataset to use for training.")
    config: TrainingRunConfig = Field(..., description="Training configuration details.")


# --- Create (API Request Body) ---
class TrainingJobCreate(TrainingJobBase):
    """Schema for creating a new training job."""
    training_job_name: str = Field(..., min_length=1, max_length=100)
    training_job_description: Optional[str] = None


# --- Update (Used internally by worker) ---
class TrainingJobUpdate(BaseModel):
    """Schema for updating a training job."""
    celery_task_id: Optional[str] = None
    status: Optional[JobStatusEnum] = None
    status_message: Optional[str] = None
    ml_model_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# --- Read (API Response) ---
class TrainingJobRead(TrainingJobBase):
    """Schema for reading training job data."""
    id: int
    celery_task_id: Optional[str] = None
    status: JobStatusEnum
    status_message: Optional[str] = None
    ml_model_id: Optional[int] = None
    ml_model: Optional[MLModelRead] = Field(
        None, description="Details of the model created by this job."
    )  # Nested model
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
        "use_enum_values": True,  # Serialize Enum member to its value
    }


# --- API Response for Job Submission ---
class TrainingJobSubmitResponse(BaseModel):
    """Response schema for training job submission."""
    job_id: int
    celery_task_id: str
    message: str = "Training job submitted successfully."


class PaginatedTrainingJobRead(BaseModel):
    """Paginated response for training jobs."""
    items: List[TrainingJobRead]
    total: int
    skip: Optional[int] = Field(
        None, description="Number of jobs skipped in the current page."
    )
    limit: Optional[int] = Field(
        None, description="Number of jobs returned in the current page."
    )