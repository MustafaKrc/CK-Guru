# shared/schemas/inference_job.py
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, AliasChoices

from shared.schemas.enums import JobStatusEnum
# Import the specific detail schema
from shared.schemas.xai import FilePredictionDetail 

# --- Result package stored in InferenceJob ---
class InferenceResultPackage(BaseModel):
    """Structured result stored in the prediction_result field of InferenceJob."""
    commit_prediction: int = Field(..., description="Aggregated prediction label for the entire commit (0 or 1).")
    max_bug_probability: float = Field(..., description="Maximum probability of being defect-prone found among analyzed instances.")
    num_files_analyzed: int = Field(..., description="Number of file/class instances analyzed within the commit.")
    # Keep details of file-level predictions here
    details: Optional[List[FilePredictionDetail]] = Field(None, description="List of prediction details for each analyzed file/class instance.")
    # REMOVED XAI from here
    error: Optional[str] = Field(None, description="Error message if prediction failed.")

class InferenceJobBase(BaseModel):
    ml_model_id: int = Field(..., description="ID of the ML model to use for inference.")
    # Flexible input: Can be a dictionary of features, S3 URI, commit hash, etc.
    # Standardizing on a dict containing commit hash for this feature
    input_reference: Dict[str, Any] = Field(..., description="Reference to input data (e.g., {'commit_hash': '...', 'repo_id': ..., 'trigger_source': 'manual'|'webhook'}).")

# --- Create (API Request Body - used internally by orchestrator) ---
class InferenceJobCreateInternal(InferenceJobBase):
    # Internal creation schema might include initial status
    status: JobStatusEnum = JobStatusEnum.PENDING
    celery_task_id: Optional[str] = None # Task ID of the *initial* ingestion task

# --- Update (Used internally by worker/orchestrator) ---
class InferenceJobUpdate(BaseModel):
    celery_task_id: Optional[str] = None # Can be updated if retried etc.
    status: Optional[JobStatusEnum] = None
    status_message: Optional[str] = None
    prediction_result: Optional[InferenceResultPackage] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(extra='ignore') # Allow extra fields if needed for flexibility

# --- Read (API Response for GET /infer/{job_id}) ---
class InferenceJobRead(InferenceJobBase):
    id: int
    celery_task_id: Optional[str] = None # Task ID of the *latest* Celery task associated
    status: JobStatusEnum
    status_message: Optional[str] = None
    prediction_result: Optional[InferenceResultPackage] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

# --- API Response for Job Submission ---
class InferenceJobSubmitResponse(BaseModel):
    job_id: int
    celery_task_id: str
    message: str = "Inference job pipeline initiated successfully."