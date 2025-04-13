# shared/schemas/inference_job.py
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field

from shared.db.models.training_job import JobStatusEnum # Reuse Enum

# --- Base ---
class InferenceJobBase(BaseModel):
    ml_model_id: int = Field(..., description="ID of the ML model to use for inference.")
    # Flexible input: Can be a dictionary of features, S3 URI, commit hash, etc.
    input_reference: Dict[str, Any] = Field(..., description="Reference to or data for input.")

# --- Create (API Request Body) ---
class InferenceJobCreate(InferenceJobBase):
    pass

# --- Update (Used internally by worker) ---
class InferenceJobUpdate(BaseModel):
    celery_task_id: Optional[str] = None
    status: Optional[JobStatusEnum] = None
    status_message: Optional[str] = None
    prediction_result: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

# --- Read (API Response) ---
class InferenceJobRead(InferenceJobBase):
    id: int
    celery_task_id: Optional[str] = None
    status: JobStatusEnum
    status_message: Optional[str] = None
    prediction_result: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
        "use_enum_values": True # Serialize Enum member to its value
    }

# --- API Response for Job Submission ---
class InferenceJobSubmitResponse(BaseModel):
    job_id: int
    celery_task_id: str
    message: str = "Inference job submitted successfully."