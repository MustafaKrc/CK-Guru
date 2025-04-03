# shared/db/models/bot_pattern.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Enum, Text, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column
from shared.db.base_class import Base
from typing import TYPE_CHECKING, Optional
import enum

if TYPE_CHECKING:
    from .repository import Repository # noqa

class PatternTypeEnum(str, enum.Enum):
    REGEX = "regex"
    WILDCARD = "wildcard"
    EXACT = "exact"

class BotPattern(Base):
    __tablename__ = "bot_patterns"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # Null repository_id means it's a global pattern
    repository_id: Mapped[int | None] = mapped_column(ForeignKey('repositories.id', ondelete="CASCADE"), nullable=True, index=True)
    pattern: Mapped[str] = mapped_column(String, nullable=False)
    pattern_type: Mapped[PatternTypeEnum] = mapped_column(Enum(PatternTypeEnum, name="pattern_type_enum"), nullable=False, default=PatternTypeEnum.EXACT)
    is_exclusion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    repository: Mapped[Optional["Repository"]] = relationship("Repository", back_populates="bot_patterns")

    __table_args__ = (
        UniqueConstraint('repository_id', 'pattern', 'pattern_type', 'is_exclusion', name='uq_repo_bot_pattern'),
        # Add check constraint if needed, e.g., ensure global patterns don't have repo_id
    )

    def __repr__(self):
        scope = f"Repo({self.repository_id})" if self.repository_id else "Global"
        exclusion = " (Exclusion)" if self.is_exclusion else ""
        return f"<BotPattern(id={self.id}, scope='{scope}', type='{self.pattern_type.value}', pattern='{self.pattern}'{exclusion})>"