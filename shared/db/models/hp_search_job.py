# shared/db/models/hp_search_job.py
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from shared.db.base_class import Base

from .training_job import JobStatusEnum  # Reuse the enum

if TYPE_CHECKING:
    from .dataset import Dataset  # noqa: F401
    from .ml_model import MLModel  # noqa: F401


class HyperparameterSearchJob(Base):
    __tablename__ = "hp_search_jobs"

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
        JSON,
        nullable=False,
        comment="Search configuration (model type, HP space, Optuna settings)",
    )

    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    optuna_study_name: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
        unique=True,
        comment="Unique name for the Optuna study",
    )

    # Results from Optuna
    best_trial_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Optuna's internal best trial ID"
    )
    best_params: Mapped[Dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    best_value: Mapped[float | None] = mapped_column(Float, nullable=True)

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
    dataset: Mapped["Dataset"] = relationship()
    best_ml_model: Mapped[Optional["MLModel"]] = relationship(
        "MLModel",
        back_populates="hp_search_job",
        # foreign_keys=[best_ml_model_id],
        uselist=False,
    )

    def __repr__(self):
        model_info = (
            f", best_trial_id={self.best_trial_id}" if self.best_trial_id else ""
        )
        return f"<HyperparameterSearchJob(id={self.id}, status='{self.status.value}', study='{self.optuna_study_name}'{model_info})>"
