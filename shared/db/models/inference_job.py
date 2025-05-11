# shared/db/models/inference_job.py
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from shared.db.base_class import Base

# Reuse JobStatusEnum from training_job or enums schema
from shared.schemas.enums import JobStatusEnum

if TYPE_CHECKING:
    from .ml_model import MLModel  # noqa: F401


class InferenceJob(Base):
    __tablename__ = "inference_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # Store the Celery Task ID of the *latest* task responsible for this job's state
    # (initially ingestion, potentially updated if retried or handed off)
    celery_task_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True, unique=False
    )  # Can be non-unique if retried
    status: Mapped[JobStatusEnum] = mapped_column(
        Enum(JobStatusEnum, name="job_status_enum"),
        nullable=False,
        default=JobStatusEnum.PENDING,
        index=True,
    )
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    ml_model_id: Mapped[int] = mapped_column(
        ForeignKey("ml_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Model used for inference",
    )
    input_reference: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="Reference to input data (e.g., {'commit_hash': 'abc...', 'repo_id': 1, 'trigger_source': 'manual'})",
    )
    prediction_result: Mapped[Dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Stored prediction output (e.g., {'prediction': 1, 'probability': 0.85})",
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
    ml_model: Mapped["MLModel"] = relationship(
        "MLModel", back_populates="inference_jobs"
    )

    def __repr__(self):
        commit = (
            self.input_reference.get("commit_hash", "N/A")[:7]
            if isinstance(self.input_reference, dict)
            else "N/A"
        )
        return f"<InferenceJob(id={self.id}, status='{self.status.value}', model_id={self.ml_model_id}, commit='{commit}')>"
