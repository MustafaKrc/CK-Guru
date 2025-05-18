# shared/schemas/bot_pattern.py
from typing import Optional

from pydantic import BaseModel, Field

from shared.db.models.bot_pattern import PatternTypeEnum  # Import Enum


class BotPatternBase(BaseModel):
    pattern: str = Field(
        ..., description="The pattern string (exact, wildcard, or regex)."
    )
    pattern_type: PatternTypeEnum = Field(
        default=PatternTypeEnum.EXACT, description="Type of the pattern."
    )
    is_exclusion: bool = Field(
        default=False,
        description="If true, matches exclude commits instead of including them for filtering.",
    )
    description: Optional[str] = Field(
        None, description="Optional description of the pattern."
    )
    repository_id: Optional[int] = Field(
        None, description="Repository ID if specific to a repo, null for global."
    )


class BotPatternCreate(BotPatternBase):
    pass


class BotPatternUpdate(BaseModel):
    pattern: Optional[str] = None
    pattern_type: Optional[PatternTypeEnum] = None
    is_exclusion: Optional[bool] = None
    description: Optional[str] = None
    # repository_id is usually not updatable, managed via endpoint path


class BotPatternRead(BotPatternBase):
    id: int

    model_config = {
        "from_attributes": True,  # Pydantic V2 way
        "use_enum_values": True,  # Serialize enums as strings
    }

class PaginatedBotPatternRead(BaseModel):
    total: int
    items: list[BotPatternRead]

    skip: Optional[int] = None
    limit: Optional[int] = None