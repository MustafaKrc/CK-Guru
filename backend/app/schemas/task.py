# backend/app/schemas/task.py
import enum
from typing import Any, Optional

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
    status: TaskStatusEnum = Field(..., description="Current high-level status of the task.")
    progress: Optional[int] = Field(None, description="Percentage progress of the task (if available).") # <<< NEW
    status_message: Optional[str] = Field(None, description="Detailed status message from the worker (if available).") # <<< NEW
    result: Any | None = Field(None, description="Final result of the task if completed successfully.")
    error: str | None = Field(None, description="Error message if the task failed.")

    model_config = {
        "json_schema_extra": {
            "examples": [
                { # Example for PROGRESS state
                    "task_id": "d3c1e0f0...",
                    "status": "STARTED", # Main state is still STARTED
                    "progress": 55,      # Progress percentage
                    "status_message": "Saving Commit Guru metrics (150/400)...", # Detailed message
                    "result": None,
                    "error": None,
                },
                { # Example for final SUCCESS with meta-data returned
                    "task_id": "e4d2f1a1...",
                    "status": "SUCCESS",
                    "progress": None, # Optional: Could be 100, but often cleared on success
                    "status_message": None, # Optional: Often cleared on success
                    "result": { # Final result payload from the task
                        "status": "Completed successfully",
                        "repository_id": 1,
                        "commit_guru_metrics_inserted": 40,
                        "ck_metrics_inserted": 512,
                        "total_commits_analyzed_guru": 40
                    },
                    "error": None,
                },
            ]
        }
    }