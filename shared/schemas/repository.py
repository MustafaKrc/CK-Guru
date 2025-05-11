from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


# Shared properties
class RepositoryBase(BaseModel):
    git_url: HttpUrl = Field(
        ..., json_schema_extra={"example": "https://github.com/user/repo.git"}
    )


# Properties to receive via API on creation
class RepositoryCreate(RepositoryBase):
    pass


# Properties to receive via API on update (optional)
class RepositoryUpdate(BaseModel):
    name: Optional[str] = None
    git_url: Optional[HttpUrl] = None

    model_config = ConfigDict(from_attributes=True)


# Properties shared by models stored in DB
class RepositoryInDBBase(RepositoryBase):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime

    # Use Pydantic V2 syntax for ORM mode
    model_config = ConfigDict(from_attributes=True)


# Properties to return to client
class RepositoryRead(RepositoryInDBBase):
    # Include counts of related items for API responses
    bot_patterns_count: Optional[int] = 0
    datasets_count: Optional[int] = 0
    github_issues_count: Optional[int] = 0


# Properties stored in DB
class RepositoryInDB(RepositoryInDBBase):
    # Add any additional fields that are stored in DB but not returned to client
    # For most repositories, this might be the same as RepositoryInDBBase
    pass
