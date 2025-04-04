# shared/db/models/cleaning_rule_definition.py
from sqlalchemy import Column, String, Text, JSON, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column
from typing import List, Dict, Any
from datetime import datetime
from shared.db.base_class import Base

class CleaningRuleDefinitionDB(Base): # add db suffix to avoid confusion with the base class
    __tablename__ = "cleaning_rule_definitions"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=[])
    is_batch_safe: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_implemented: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    last_updated_by: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )