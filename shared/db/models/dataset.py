# shared/db/models/dataset.py
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from shared.db.base_class import Base
from shared.schemas.enums import DatasetStatusEnum

if TYPE_CHECKING:
    from .repository import Repository  # noqa


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    num_rows: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Number of rows in the generated dataset"
    )

    # Store configuration as JSON
    config: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    # Example config structure:
    # {
    #   "feature_columns": ["list", "of", "features"],
    #   "target_column": "is_buggy",
    #   "cleaning_rules": [{"name": "rule_id", "enabled": true, "params": {...}}]
    # }

    feature_selection_config: Mapped[Dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Configuration for the feature selection algorithm, e.g., {'name': 'mrmr', 'params': {'k': 20}}",
    )

    status: Mapped[DatasetStatusEnum] = mapped_column(
        Enum(DatasetStatusEnum, name="dataset_status_enum"),
        nullable=False,
        default=DatasetStatusEnum.PENDING,
        index=True,
    )
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # Relative path within persistent volume

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    repository: Mapped["Repository"] = relationship(
        "Repository", back_populates="datasets"
    )

    background_data_path: Mapped[str | None] = mapped_column(
        String, nullable=True, comment="Path to sampled background data for XAI"
    )

    def __repr__(self):
        return f"<Dataset(id={self.id}, name='{self.name}', repo_id={self.repository_id}, status='{self.status.value}')>"
