# shared/schemas/ml_model.py
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from shared.schemas.enums import ModelTypeEnum


# --- Base ---
class MLModelBase(BaseModel):
    name: str = Field(..., description="Logical name for the model.")
    model_type: ModelTypeEnum = Field(
        ..., description="Type/architecture of the model."
    )
    description: Optional[str] = Field(None, description="Optional description.")
    hyperparameters: Optional[Dict[str, Any]] = Field(
        None, description="Hyperparameters used for this specific instance."
    )
    performance_metrics: Optional[Dict[str, Any]] = Field(
        None, description="Key performance metrics (e.g., accuracy, f1)."
    )
    dataset_id: Optional[int] = Field(
        None, description="ID of the dataset used for training/evaluation."
    )


# --- Create (Used internally by worker, maybe not direct API?) ---
# Usually created implicitly by training/search jobs
class MLModelCreate(MLModelBase):
    version: int = Field(..., description="Version number for this model name.")
    s3_artifact_path: Optional[str] = Field(
        None, description="Initial path before final upload (if needed)."
    )
    training_job_id: Optional[int] = None
    hp_search_job_id: Optional[int] = None


# --- Update (Maybe for description or adding metrics later?) ---
class MLModelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    performance_metrics: Optional[Dict[str, Any]] = None
    # Other fields are typically immutable after creation


# --- Read (Returned by API) ---
class MLModelRead(MLModelBase):
    id: int
    version: int
    s3_artifact_path: Optional[str] = Field(
        None, description="URI to the saved model artifact."
    )
    # Include related job IDs if useful for client
    training_job_id: Optional[int] = None
    hp_search_job_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,  # Pydantic V2+ ORM mode
    }

class PaginatedMLModelRead(BaseModel):
    items: List[MLModelRead]
    total: int
    skip: Optional[int] = None
    limit: Optional[int] = None 
