# backend/app/schemas/task.py
import enum
from typing import Any
from pydantic import BaseModel, Field

class TaskResponse(BaseModel):
    """Response model when a background task is successfully initiated."""
    task_id: str = Field(..., description="The unique ID of the background task.")
    message: str = Field("Task successfully submitted.", description="Informational message.")

class TaskStatusEnum(str, enum.Enum): # Use standard Python enum
    PENDING = "PENDING"
    RECEIVED = "RECEIVED" # Task received by a worker
    STARTED = "STARTED"   # Task started execution
    SUCCESS = "SUCCESS"   # Task completed successfully
    FAILURE = "FAILURE"   # Task failed
    RETRY = "RETRY"     # Task is being retried
    REVOKED = "REVOKED"   # Task was revoked.

class TaskStatusResponse(BaseModel):
    """Response model for checking the status of a background task."""
    task_id: str = Field(..., description="The unique ID of the background task.")
    status: TaskStatusEnum = Field(..., description="Current status of the task.")
    # Use Union for result, allowing it to be None or specific types later
    result: Any | None = Field(None, description="Result of the task if completed successfully.")
    error: str | None = Field(None, description="Error message if the task failed.")

    model_config = { # Pydantic V2 config
        "json_schema_extra": {
            "examples": [
                {
                    "task_id": "b1a9c8f8-7d6e-4b3c-9a1f-0e2d1b3c4d5e",
                    "status": "PENDING",
                    "result": None,
                    "error": None,
                },
                {
                    "task_id": "b1a9c8f8-7d6e-4b3c-9a1f-0e2d1b3c4d5e",
                    "status": "SUCCESS",
                    "result": {"dataset_path": "/app/persistent_data/datasets/repo_1/dataset_20250401.csv"},
                    "error": None,
                },
                 {
                    "task_id": "c2b0d9g9-8e7f-5c4d-0b2g-1f3e2c4d5e6f",
                    "status": "FAILURE",
                    "result": None,
                    "error": "Failed to clone repository: Authentication required.",
                },
            ]
        }
    }