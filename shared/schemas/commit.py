# shared/schemas/commit.py
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import CommitIngestionStatusEnum, FileChangeTypeEnum
from .inference_job import InferenceJobRead


class CommitFileDiffRead(BaseModel):
    id: int
    file_path: str
    change_type: FileChangeTypeEnum
    old_path: Optional[str] = None
    diff_text: str

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class CommitDetailsRead(BaseModel):
    id: int
    commit_hash: str
    author_name: str
    author_email: str
    author_date: datetime
    message: str
    parents: List[str]
    stats_insertions: int
    stats_deletions: int
    stats_files_changed: int
    file_diffs: List[CommitFileDiffRead]

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class CommitPageResponse(BaseModel):
    ingestion_status: CommitIngestionStatusEnum
    details: Optional[CommitDetailsRead] = None
    inference_jobs: List[InferenceJobRead] = Field(default_factory=list)
    celery_ingestion_task_id: Optional[str] = None


class CommitListItem(BaseModel):
    commit_hash: str
    author_name: str
    author_date: datetime
    message_short: str
    ingestion_status: CommitIngestionStatusEnum

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class PaginatedCommitList(BaseModel):
    items: List[CommitListItem]
    total: int
    skip: Optional[int] = None
    limit: Optional[int] = None