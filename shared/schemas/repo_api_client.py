# shared/schemas/repo_api_client.py
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class RepoApiResponseStatus:
    """Enum-like constants for abstracted API status."""

    OK = 200  # Data retrieved successfully
    NOT_MODIFIED = 304  # Data not modified since last ETag check
    NOT_FOUND = 404  # Resource not found (includes 410 Gone)
    RATE_LIMITED = 429  # Rate limit exceeded (or 403 with specific headers)
    ERROR = 500  # General server/client error


class RepoApiClientResponse(BaseModel):
    """Generic response structure for repository API clients."""

    status: int = Field(
        ...,
        description=f"Abstracted status code ({'/'.join(str(v) for v in vars(RepoApiResponseStatus) if not v.startswith('_'))})",
    )
    json_data: Optional[Dict[str, Any]] = Field(
        None, description="Parsed JSON payload, if available and successful."
    )
    etag: Optional[str] = Field(
        None, description="ETag associated with the response, if any."
    )
    error_message: Optional[str] = Field(
        None, description="Error details if status indicates failure."
    )
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[int] = None

    # Helper property (optional)
    @property
    def is_successful(self) -> bool:
        return self.status in [
            RepoApiResponseStatus.OK,
            RepoApiResponseStatus.NOT_MODIFIED,
        ]
