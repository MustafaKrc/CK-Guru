# shared/schemas/xai_job.py
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import XAIStatusEnum, XAITypeEnum

# Import specific XAI result data schemas if needed for validation, or use Any/Dict
# from .xai import SHAPResultData, LIMEResultData, ...


class XAIResultBase(BaseModel):
    inference_job_id: int = Field(..., description="ID of the parent InferenceJob.")
    xai_type: XAITypeEnum = Field(..., description="Type of explanation generated.")


class XAIResultCreate(XAIResultBase):
    status: XAIStatusEnum = Field(default=XAIStatusEnum.PENDING)
    celery_task_id: Optional[str] = Field(
        None, description="Celery task ID for this specific XAI generation."
    )


class XAIResultUpdate(BaseModel):
    status: Optional[XAIStatusEnum] = None
    status_message: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = Field(
        None, description="JSON containing the structured explanation data."
    )  # Store as generic dict
    celery_task_id: Optional[str] = None  # Can be updated if retried
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(extra="ignore")


class XAIResultRead(XAIResultBase):
    id: int
    status: XAIStatusEnum
    status_message: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = Field(
        None, description="The generated explanation data."
    )  # Return as generic dict
    celery_task_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class XAITriggerResponse(BaseModel):
    task_id: Optional[str] = Field(
        None, description="Celery task ID for the XAI orchestration."
    )
    message: str = Field(
        ..., description="Message indicating the result of the trigger."
    )
