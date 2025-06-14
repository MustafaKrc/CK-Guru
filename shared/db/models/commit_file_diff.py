# shared/db/models/commit_file_diff.py
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db.base_class import Base
from shared.schemas.enums import FileChangeTypeEnum

if TYPE_CHECKING:
    from .commit_details import CommitDetails


class CommitFileDiff(Base):
    __tablename__ = "commit_file_diffs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    commit_detail_id: Mapped[int] = mapped_column(
        ForeignKey("commit_details.id", ondelete="CASCADE"), index=True
    )
    file_path: Mapped[str] = mapped_column(String)
    change_type: Mapped[FileChangeTypeEnum] = mapped_column(
        Enum(FileChangeTypeEnum, name="file_change_type_enum")
    )
    old_path: Mapped[str | None] = mapped_column(String)
    diff_text: Mapped[str] = mapped_column(Text)
    insertions: Mapped[int] = mapped_column(Integer)
    deletions: Mapped[int] = mapped_column(Integer)

    commit_detail: Mapped["CommitDetails"] = relationship(
        "CommitDetails", back_populates="file_diffs"
    )
