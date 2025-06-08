# shared/db/models/bot_pattern.py
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db.base_class import Base

if TYPE_CHECKING:
    from .repository import Repository  # noqa


class BotPattern(Base):
    __tablename__ = "bot_patterns"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # Null repository_id means it's a global pattern
    repository_id: Mapped[int | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=True, index=True
    )
    pattern: Mapped[str] = mapped_column(String, nullable=False, comment="The regular expression pattern.")
    is_exclusion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="If true, matches are explicitly NOT bots.")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    repository: Mapped[Optional["Repository"]] = relationship(
        "Repository", back_populates="bot_patterns"
    )

    __table_args__ = (
        UniqueConstraint("repository_id", "pattern", name="uq_repo_bot_pattern"),
    )

    def __repr__(self):
        scope = f"Repo({self.repository_id})" if self.repository_id else "Global"
        exclusion = " (Exclusion)" if self.is_exclusion else ""
        return f"<BotPattern(id={self.id}, scope='{scope}', pattern='{self.pattern}'{exclusion})>"