# shared/db/models/feature_selection_definition.py
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import JSON, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from shared.db.base_class import Base


class FeatureSelectionDefinitionDB(Base):
    """SQLAlchemy model for storing feature selection algorithm definitions."""

    __tablename__ = "feature_selection_definitions"

    name: Mapped[str] = mapped_column(
        String, primary_key=True, comment="Unique identifier name, e.g., 'cbfs'"
    )
    display_name: Mapped[str] = mapped_column(
        String, nullable=False, comment="User-friendly name for the UI"
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=[]
    )
    is_implemented: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Is the algorithm implemented and available in any worker?",
    )
    last_updated_by: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Identifier of the worker that last synced this record",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
