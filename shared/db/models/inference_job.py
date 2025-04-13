# shared/db/models/inference_job.py
from typing import TYPE_CHECKING, Dict, Any, Optional
from datetime import datetime

from sqlalchemy import (Column, Integer, String, ForeignKey, Text, JSON,
                      DateTime, Enum, Index)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column

from shared.db.base_class import Base
from .training_job import JobStatusEnum # Reuse the enum

if TYPE_CHECKING:
    from .ml_model import MLModel # noqa: F401

class InferenceJob(Base):
    __tablename__ = "inference_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    celery_task_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True, unique=True)
    status: Mapped[JobStatusEnum] = mapped_column(Enum(JobStatusEnum, name="job_status_enum"), nullable=False, default=JobStatusEnum.PENDING, index=True)
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    ml_model_id: Mapped[int] = mapped_column(ForeignKey('ml_models.id', ondelete="CASCADE"), nullable=False, index=True,
                                               comment="Model used for inference")
    input_reference: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False,
                                                             comment="Reference to input data (e.g., commit hash, feature dict, S3 path)")
    prediction_result: Mapped[Dict[str, Any] | None] = mapped_column(JSON, nullable=True,
                                                                    comment="Stored prediction output")

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # --- Relationships ---
    ml_model: Mapped["MLModel"] = relationship("MLModel", back_populates="inference_jobs")

    def __repr__(self):
        return f"<InferenceJob(id={self.id}, status='{self.status.value}', model_id={self.ml_model_id})>"