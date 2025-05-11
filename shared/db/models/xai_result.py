# shared/db/models/xai_result.py
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from shared.db.base_class import Base

# Import the enums
from shared.schemas.enums import XAIStatusEnum, XAITypeEnum

if TYPE_CHECKING:
    from .inference_job import InferenceJob  # noqa: F401


class XAIResult(Base):
    __tablename__ = "xai_results"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    inference_job_id: Mapped[int] = mapped_column(
        ForeignKey(
            "inference_jobs.id", ondelete="CASCADE"
        ),  # Cascade delete if inference job is removed
        nullable=False,
        index=True,
    )
    xai_type: Mapped[XAITypeEnum] = mapped_column(
        Enum(XAITypeEnum, name="xai_type_enum"), nullable=False, index=True
    )
    status: Mapped[XAIStatusEnum] = mapped_column(
        Enum(XAIStatusEnum, name="xai_status_enum"),
        nullable=False,
        default=XAIStatusEnum.PENDING,
        index=True,
    )
    # Stores the structured result (SHAP details, LIME weights, etc.)
    result_data: Mapped[Dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )  # Task ID for this specific XAI job

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
    inference_job: Mapped["InferenceJob"] = (
        relationship()
    )  # No back-pop needed on InferenceJob unless listing XAIResults

    # --- Constraints ---
    __table_args__ = (
        UniqueConstraint(
            "inference_job_id", "xai_type", name="uq_inference_job_xai_type"
        ),
        Index(
            "ix_xai_results_job_id_type", "inference_job_id", "xai_type"
        ),  # Combined index
    )

    def __repr__(self):
        return f"<XAIResult(id={self.id}, job_id={self.inference_job_id}, type='{self.xai_type.value}', status='{self.status.value}')>"
