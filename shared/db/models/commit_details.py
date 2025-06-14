# shared/db/models/commit_details.py
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from shared.db.base_class import Base
from shared.schemas.enums import CommitIngestionStatusEnum

if TYPE_CHECKING:
    from .commit_file_diff import CommitFileDiff
    from .repository import Repository


class CommitDetails(Base):
    __tablename__ = "commit_details"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    commit_hash: Mapped[str] = mapped_column(String(40), index=True)

    # Metadata from git
    author_name: Mapped[str] = mapped_column(String)
    author_email: Mapped[str] = mapped_column(String)
    author_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    committer_name: Mapped[str] = mapped_column(String)
    committer_email: Mapped[str] = mapped_column(String)
    committer_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    message: Mapped[str] = mapped_column(Text)
    parents: Mapped[Dict] = mapped_column(JSON, comment="List of parent hashes")
    stats_insertions: Mapped[int] = mapped_column(Integer)
    stats_deletions: Mapped[int] = mapped_column(Integer)
    stats_files_changed: Mapped[int] = mapped_column(Integer)

    # Status tracking for this specific ingestion
    ingestion_status: Mapped[CommitIngestionStatusEnum] = mapped_column(
        Enum(CommitIngestionStatusEnum, name="commit_ingestion_status_enum"),
        default=CommitIngestionStatusEnum.PENDING.value,
        index=True,
    )
    celery_ingestion_task_id: Mapped[str | None] = mapped_column(String, index=True)
    status_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    file_diffs: Mapped[List["CommitFileDiff"]] = relationship(
        "CommitFileDiff", back_populates="commit_detail", cascade="all, delete-orphan"
    )
    repository: Mapped["Repository"] = relationship("Repository")

    __table_args__ = (
        UniqueConstraint("repository_id", "commit_hash", name="uq_repo_commit_hash"),
    )
