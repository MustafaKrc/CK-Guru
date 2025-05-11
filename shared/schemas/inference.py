# shared/schemas/inference.py
from typing import Dict, List

from pydantic import BaseModel, Field, HttpUrl


class ManualInferenceRequest(BaseModel):
    """Request body for the manual inference endpoint."""

    repo_id: int = Field(..., description="The database ID of the repository.")
    target_commit_hash: str = Field(
        ...,
        min_length=7,  # Allow short hashes for user convenience initially
        max_length=40,
        description="The target commit hash for inference (full or short).",
        examples=["a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0", "a1b2c3d"],
    )
    ml_model_id: int = Field(..., description="The database ID of the ML model to use.")


class InferenceTriggerResponse(BaseModel):
    """Response containing IDs after triggering an inference pipeline."""

    inference_job_id: int = Field(
        ..., description="The ID of the created InferenceJob record."
    )
    initial_task_id: str = Field(
        ..., description="The Celery task ID for the initial feature extraction step."
    )


# Basic structure for GitHub Push Event Payload (add more fields as needed)
class GitHubRepositoryInfo(BaseModel):
    id: int
    name: str
    full_name: str
    html_url: HttpUrl


class GitHubCommitInfo(BaseModel):
    id: str  # The commit hash
    message: str
    # Add other fields like author, committer, timestamp if needed


class GitHubPushPayload(BaseModel):
    ref: str
    before: str
    after: str  # The commit hash we are interested in
    repository: GitHubRepositoryInfo
    pusher: Dict[str, str]  # Simplified pusher info
    commits: List[GitHubCommitInfo] = []
    # Add other fields from the push event payload if needed
