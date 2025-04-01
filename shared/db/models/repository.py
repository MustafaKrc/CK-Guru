from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from shared.db.base_class import Base
from datetime import datetime
from typing import List # Use List from typing for relationships

class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    git_url: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # --- Relationships (Add later as needed) ---
    # datasets: Mapped[List["Dataset"]] = relationship("Dataset", back_populates="repository", cascade="all, delete-orphan")
    # models: Mapped[List["Model"]] = relationship("Model", back_populates="repository", cascade="all, delete-orphan")
    # inference_results: Mapped[List["InferenceResult"]] = relationship("InferenceResult", back_populates="repository", cascade="all, delete-orphan")
    # pipeline_config: Mapped["PipelineConfiguration"] = relationship("PipelineConfiguration", back_populates="repository", uselist=False, cascade="all, delete-orphan")

    # Add UniqueConstraint if needed at the table level
    __table_args__ = (UniqueConstraint('git_url', name='uq_repository_git_url'),)

    def __repr__(self):
        return f"<Repository(id={self.id}, name='{self.name}', git_url='{self.git_url}')>"