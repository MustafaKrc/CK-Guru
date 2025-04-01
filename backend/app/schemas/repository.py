from pydantic import BaseModel, HttpUrl, Field, ConfigDict
from datetime import datetime
from typing import Optional

# Shared properties
class RepositoryBase(BaseModel):
    git_url: HttpUrl = Field(..., example="https://github.com/user/repo.git")

# Properties to receive via API on creation
class RepositoryCreate(RepositoryBase):
    pass

# Properties to receive via API on update (optional)
class RepositoryUpdate(BaseModel):
   # Define fields that can be updated, e.g.:
   # name: Optional[str] = None
   pass # Nothing updatable for now

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
    pass

# Properties stored in DB
class RepositoryInDB(RepositoryInDBBase):
   pass