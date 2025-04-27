# shared/schemas/inference_job.py
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

# Assuming JobStatusEnum is in shared.schemas.enums
from shared.schemas.enums import JobStatusEnum

# --- Base ---
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
    prediction_result: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(extra='ignore') # Allow extra fields if needed for flexibility

# --- Read (API Response for GET /infer/{job_id}) ---
class InferenceJobRead(InferenceJobBase):
    id: int
    celery_task_id: Optional[str] = None # Task ID of the *latest* Celery task associated
    status: JobStatusEnum
    status_message: Optional[str] = None
    prediction_result: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True # Serialize Enum member to its value
    )

# --- API Response for Job Submission (used by manual endpoint) ---
class InferenceJobSubmitResponse(BaseModel):
    job_id: int
    celery_task_id: str # The ID of the initial ingestion task
    message: str = "Inference job pipeline initiated successfully."