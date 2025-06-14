# shared/db/models/ml_model_type_definition.py
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, Column, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from shared.db.base_class import Base


class MLModelTypeDefinitionDB(Base):
    __tablename__ = "ml_model_type_definitions"

    # Store as string, not enum, for better compatibility
    type_name: str = Column(
        String,
        primary_key=True,
        index=True,
        comment="Internal name, e.g., from ModelTypeEnum",
    )
    display_name: str = Column(
        String, nullable=False, comment="User-friendly display name"
    )
    description: Optional[str] = Column(
        Text, nullable=True, comment="Description of the model type"
    )

    hyperparameter_schema: Dict[str, Any] = Column(
        JSONB, nullable=False, comment="Schema defining configurable hyperparameters"
    )

    is_enabled: bool = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="If this model type is available for selection",
    )
    last_updated_by: Optional[str] = Column(
        String,
        nullable=True,
        comment="Identifier of the worker/process that last updated this record",
    )

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self):
        return f"<MLModelTypeDefinitionDB(type_name='{self.type_name}', display_name='{self.display_name}', is_enabled={self.is_enabled})>"
