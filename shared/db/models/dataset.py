# shared/db/models/dataset.py
import enum
from typing import TYPE_CHECKING, Dict, Any, List
from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, Text, JSON, DateTime, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column

from shared.db.base_class import Base

if TYPE_CHECKING:
    from .repository import Repository # noqa

class DatasetStatusEnum(str, enum.Enum):
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"

class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey('repositories.id', ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Store configuration as JSON
    config: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    # Example config structure:
    # {
    #   "feature_columns": ["list", "of", "features"],
    #   "target_column": "is_buggy",
    #   "cleaning_rules": [{"name": "rule_id", "enabled": true, "params": {...}}]
    # }

    status: Mapped[DatasetStatusEnum] = mapped_column(Enum(DatasetStatusEnum, name="dataset_status_enum"), nullable=False, default=DatasetStatusEnum.PENDING, index=True)
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String, nullable=True) # Relative path within persistent volume

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    repository: Mapped["Repository"] = relationship("Repository", back_populates="datasets")

    def __repr__(self):
        return f"<Dataset(id={self.id}, name='{self.name}', repo_id={self.repository_id}, status='{self.status.value}')>"