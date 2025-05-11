# shared/db/models/training_job.py
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from shared.db.base_class import Base
from shared.schemas.enums import JobStatusEnum

if TYPE_CHECKING:
    from .dataset import Dataset  # noqa: F401
    from .ml_model import MLModel  # noqa: F401


class TrainingJob(Base):
    __tablename__ = "training_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    celery_task_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True, unique=True
    )
    status: Mapped[JobStatusEnum] = mapped_column(
        Enum(JobStatusEnum, name="job_status_enum"),
        nullable=False,
        default=JobStatusEnum.PENDING,
        index=True,
    )
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[Dict[str, Any]] = mapped_column(
        JSON, nullable=False, comment="Training configuration used"
    )

    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # --- Relationships ---
    dataset: Mapped["Dataset"] = (
        relationship()
    )  # No back_populates needed unless Dataset lists jobs
    ml_model: Mapped[Optional["MLModel"]] = relationship(
        "MLModel",
        back_populates="training_job",
        # foreign_keys=[ml_model_id],
        uselist=False,
    )

    def __repr__(self):
        model_info = f", model_id={self.ml_model_id}" if self.ml_model_id else ""
        return f"<TrainingJob(id={self.id}, status='{self.status.value}'{model_info})>"
