# shared/db/models/commit_guru_metric.py
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import (
    ARRAY,
    JSON,
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db.base_class import Base

# stop formatters deleting this import
# noinspection PyUnresolvedReferences
from .commit_github_issue_association import (  # noqa: F401
    commit_github_issue_association_table,
)

if TYPE_CHECKING:
    from .github_issue import GitHubIssue  # noqa: F401
    from .repository import Repository  # noqa: F401


class CommitGuruMetric(Base):
    __tablename__ = "commit_guru_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    commit_hash: Mapped[str] = mapped_column(String(40), nullable=False, index=True)

    # --- Contextual Information ---
    parent_hashes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    author_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    author_email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    author_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    author_date_unix_timestamp: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True
    )
    commit_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Bug Linking & Keyword Info ---
    is_buggy: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    fix: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    # Renamed from fixes, holds hashes of commits *this commit* fixes (if it's a buggy commit)
    fixing_commit_hashes: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )

    # --- Commit Information ---
    files_changed: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String), nullable=True
    )

    # --- Commit Guru Metrics ---
    ns: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    nd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    nf: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    entropy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    la: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ld: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ndev: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    age: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    nuc: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rexp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sexp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # --- Relationships ---
    repository: Mapped["Repository"] = relationship(
        "Repository"
    )  # Add back_populates if needed on Repository

    # Many-to-Many relationship with GitHubIssue
    # Corrected secondary table name reference
    github_issues: Mapped[List["GitHubIssue"]] = relationship(
        "GitHubIssue",
        secondary="commit_github_issue_association",
        back_populates="commit_metrics",
        lazy="selectin",  # Or 'select' or 'joined' depending on query needs
    )

    # --- Table Args ---
    __table_args__ = (
        UniqueConstraint("repository_id", "commit_hash", name="uq_commit_guru_metric"),
    )

    def __repr__(self):
        buggy_status = "Buggy" if self.is_buggy else "Not Buggy"
        fix_info = "Fix" if self.fix else ""
        # Note: Accessing self.github_issues here might trigger a lazy load
        # issue_count = len(self.github_issues) if self.id else 0 # Check id avoids query before flush
        # issue_info = f" Issues linked: {issue_count}" if issue_count > 0 else ""
        # Avoid accessing lazy loaded relationship in repr
        return (
            f"<CommitGuruMetric(repo={self.repository_id}, "
            f"commit='{self.commit_hash[:7]}', {buggy_status} {fix_info})>"
        )
