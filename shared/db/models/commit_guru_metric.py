# shared/db/models/commit_guru_metric.py
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, ForeignKey, BigInteger, JSON, Index, UniqueConstraint, Text
) # Import Text
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional, List, Dict, Any
from datetime import datetime

from shared.db.base_class import Base
from shared.db.models.repository import Repository
# No need to import Repository here if only using string reference in Mapped relationship

class CommitGuruMetric(Base):
    __tablename__ = 'commit_guru_metrics'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey('repositories.id'), nullable=False, index=True)
    commit_hash: Mapped[str] = mapped_column(String(40), nullable=False, index=True)

    # --- Contextual Information ---
    parent_hashes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    author_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    author_email: Mapped[Optional[str]] = mapped_column(String, nullable=True) 
    author_date: Mapped[Optional[str]] = mapped_column(String, nullable=True) 
    author_date_unix_timestamp: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    commit_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Bug Linking & Keyword Info ---
    is_buggy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True) # Renamed from contains_bug
    fix: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    fixing_commit_hashes: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True) # Renamed from fixes
    # linked: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True) # Deferring 'linked' status

    # --- Commit Information ---
    files_changed: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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

    # --- Deferred Columns ---
    # classification: Mapped[Optional[str]] = mapped_column(String, nullable=True) # Requires classifier logic
    # glm_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # Requires GLM logic

    # --- Relationships ---
    # Use string reference to avoid circular import if Repository imports CommitGuruMetric
    repository: Mapped["Repository"] = relationship("Repository")

    # --- Table Args ---
    __table_args__ = (UniqueConstraint('repository_id', 'commit_hash', name='uq_commit_guru_metric'),)

    def __repr__(self):
        buggy_status = "Buggy" if self.is_buggy else "Not Buggy"
        fix = "Fix" if self.fix else ""
        return f"<CommitGuruMetric(repo={self.repository_id}, commit='{self.commit_hash[:7]}', {buggy_status} {fix})>"