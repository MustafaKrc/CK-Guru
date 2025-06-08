# shared/schemas/bot_pattern.py
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class BotPatternBase(BaseModel):
    pattern: str = Field(..., description="The regex pattern to match against author names.")
    is_exclusion: bool = Field(False, description="If true, this pattern defines an exception and matching authors will be kept.")
    description: Optional[str] = Field(None, description="A description of what this pattern does.")


class BotPatternCreate(BotPatternBase):
    repository_id: Optional[int] = Field(None, description="The repository ID for a specific pattern. Leave null for a global pattern.")


class BotPatternUpdate(BaseModel):
    pattern: Optional[str] = None
    is_exclusion: Optional[bool] = None
    description: Optional[str] = None


class BotPatternRead(BotPatternBase):
    id: int
    repository_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedBotPatternRead(BaseModel):
    total: int
    items: List[BotPatternRead]