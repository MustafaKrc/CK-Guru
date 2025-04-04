# shared/db/models/repository.py
from typing import List, TYPE_CHECKING
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column

from shared.db.base_class import Base

if TYPE_CHECKING:
    from .github_issue import GitHubIssue # noqa: F401
    from.bot_pattern import BotPattern
    from.dataset import Dataset

class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    git_url: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    bot_patterns: Mapped[List["BotPattern"]] = relationship("BotPattern", back_populates="repository", cascade="all, delete-orphan")
    datasets: Mapped[List["Dataset"]] = relationship("Dataset", back_populates="repository", cascade="all, delete-orphan")
    github_issues: Mapped[List["GitHubIssue"]] = relationship("GitHubIssue", back_populates="repository", cascade="all, delete-orphan")


    # --- Relationships ---
    github_issues: Mapped[List["GitHubIssue"]] = relationship(
        "GitHubIssue",
        back_populates="repository",
        cascade="all, delete-orphan" # Delete issues if repo is deleted
    )
    # Add relationship to CommitGuruMetric if needed for querying from repo side
    # commit_guru_metrics: Mapped[List["CommitGuruMetric"]] = relationship(
    #    "CommitGuruMetric", back_populates="repository", cascade="all, delete-orphan"
    # )

    __table_args__ = (UniqueConstraint('git_url', name='uq_repository_git_url'),)

    def __repr__(self):
        return f"<Repository(id={self.id}, name='{self.name}', git_url='{self.git_url}')>"