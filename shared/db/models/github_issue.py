# shared/db/models/github_issue.py
from datetime import datetime
import logging

from sqlalchemy import (Column, Integer, String, BigInteger, DateTime, ForeignKey,
                      UniqueConstraint, Index)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from typing import Optional, List, TYPE_CHECKING

from shared.db.base_class import Base

# Avoid circular imports for type checking relationships
if TYPE_CHECKING:
    from .repository import Repository  # noqa: F401
    from .commit_guru_metric import CommitGuruMetric # noqa: F401

logger = logging.getLogger(__name__)

class GitHubIssue(Base):
    __tablename__ = 'github_issues'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # Link to the repository this issue belongs to
    repository_id: Mapped[int] = mapped_column(
        ForeignKey('repositories.id', ondelete='CASCADE'), # Cascade delete if repo is deleted
        nullable=False,
        index=True
    )
    # The issue number within the specific repository (e.g., 123)
    issue_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # GitHub's global, immutable ID for the issue (highly recommended)
    github_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, unique=True)
    # Current state ('open', 'closed', 'unknown', 'deleted')
    state: Mapped[str] = mapped_column(String(20), nullable=False, default='unknown', server_default='unknown')
    # Timestamps (storing as Unix epoch seconds for consistency with other parts)
    created_at_timestamp: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    closed_at_timestamp: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # URLs for reference
    api_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    html_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Caching metadata
    last_fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now() # Automatically update on ORM update
    )
    etag: Mapped[Optional[str]] = mapped_column(String, nullable=True) # Store the ETag header

    # --- Relationships ---
    repository: Mapped["Repository"] = relationship(back_populates="github_issues")

    # Many-to-Many relationship with CommitGuruMetric
    # Corrected secondary table name reference
    commit_metrics: Mapped[List["CommitGuruMetric"]] = relationship(
        secondary="commit_github_issue_association",
        back_populates="github_issues"
    )

    # --- Constraints and Indexes ---
    __table_args__ = (
        UniqueConstraint('repository_id', 'issue_number', name='uq_repo_issue_number'),
        # Optional: Index on github_id if frequently queried directly
        # Index('ix_github_issues_github_id', 'github_id'),
    )

    def __repr__(self):
        return (f"<GitHubIssue(repo_id={self.repository_id}, "
                f"number=#{self.issue_number}, state='{self.state}')>")