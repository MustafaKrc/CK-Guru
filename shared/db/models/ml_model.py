# shared/db/models/ml_model.py
from typing import TYPE_CHECKING, Dict, Any, List, Optional
from datetime import datetime

from sqlalchemy import (Column, Integer, String, ForeignKey, Text, JSON,
                      DateTime, Float, UniqueConstraint)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column

from shared.db.base_class import Base

if TYPE_CHECKING:
    from .dataset import Dataset  # noqa: F401
    from .training_job import TrainingJob # noqa: F401
    from .hp_search_job import HyperparameterSearchJob # noqa: F401
    from .inference_job import InferenceJob # noqa: F401

class MLModel(Base):
    __tablename__ = "ml_models"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True,
                                    comment="Logical name for the model (e.g., commit_defect_classifier)")
    version: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=1,
                                         comment="Version number for this model name")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_type: Mapped[str] = mapped_column(String, nullable=False, index=True,
                                             comment="Type of the model (e.g., sklearn_randomforest, pytorch_cnn)")
    s3_artifact_path: Mapped[str | None] = mapped_column(String, nullable=True, unique=True,
                                                         comment="URI to the saved model artifact in S3/MinIO")

    # Link to the source data/jobs
    dataset_id: Mapped[int | None] = mapped_column(
        ForeignKey('datasets.id', ondelete="SET NULL"), # Link to the dataset used for training
        nullable=True, # Allow null if model wasn't trained from a managed dataset
        index=True,
        comment="Dataset used for training/evaluation (optional)"
    )
    training_job_id: Mapped[int | None] = mapped_column(ForeignKey('training_jobs.id', ondelete="SET NULL"), nullable=True, index=True,
                                                         comment="Training job that created this model (optional)")
    hp_search_job_id: Mapped[int | None] = mapped_column(ForeignKey('hp_search_jobs.id', ondelete="SET NULL"), nullable=True, index=True,
                                                           comment="HP search job that resulted in this model (optional)")

    # Model details
    hyperparameters: Mapped[Dict[str, Any] | None] = mapped_column(JSON, nullable=True,
                                                                  comment="Hyperparameters used for this specific model instance")
    performance_metrics: Mapped[Dict[str, Any] | None] = mapped_column(JSON, nullable=True,
                                                                      comment="Key performance metrics (e.g., accuracy, f1)")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # --- Relationships ---
    dataset: Mapped[Optional["Dataset"]] = relationship() # No back_populates needed unless Dataset needs to list models
    training_job: Mapped[Optional["TrainingJob"]] = relationship(
        "TrainingJob",
        back_populates="ml_model",
        foreign_keys=[training_job_id],
        uselist=False
    )
    hp_search_job: Mapped[Optional["HyperparameterSearchJob"]] = relationship(
        "HyperparameterSearchJob",
        back_populates="best_ml_model",
        foreign_keys=[hp_search_job_id],
        uselist=False
    )
    inference_jobs: Mapped[List["InferenceJob"]] = relationship("InferenceJob", back_populates="ml_model") # Models used in many inferences

    __table_args__ = (
        UniqueConstraint('name', 'version', name='uq_ml_model_name_version'),
    )

    def __repr__(self):
        return f"<MLModel(id={self.id}, name='{self.name}', version={self.version}, type='{self.model_type}')>"