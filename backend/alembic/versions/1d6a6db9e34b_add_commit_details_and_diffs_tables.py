"""add_commit_details_and_diffs_tables

Revision ID: 1d6a6db9e34b
Revises: d9a14200cce1
Create Date: 2025-06-07 18:22:16.557192

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "1d6a6db9e34b"
down_revision: Union[str, None] = "d9a14200cce1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Creates the commit_details and commit_file_diffs tables using SQLAlchemy constructs."""
    # Define the ENUM types using SQLAlchemy's Enum construct.
    # Alembic will translate this into CREATE TYPE for PostgreSQL.
    commit_ingestion_status_enum = sa.Enum(
        "PENDING", "RUNNING", "COMPLETE", "FAILED", name="commit_ingestion_status_enum"
    )
    file_change_type_enum = sa.Enum(
        "A", "M", "D", "R", "C", "T", "U", "X", "B", name="file_change_type_enum"
    )

    # Create the commit_details table
    op.create_table(
        "commit_details",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("commit_hash", sa.String(length=40), nullable=False),
        sa.Column("author_name", sa.String(), nullable=False),
        sa.Column("author_email", sa.String(), nullable=False),
        sa.Column("author_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committer_name", sa.String(), nullable=False),
        sa.Column("committer_email", sa.String(), nullable=False),
        sa.Column("committer_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("parents", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("stats_insertions", sa.Integer(), nullable=False),
        sa.Column("stats_deletions", sa.Integer(), nullable=False),
        sa.Column("stats_files_changed", sa.Integer(), nullable=False),
        sa.Column(
            "ingestion_status",
            commit_ingestion_status_enum,
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("celery_ingestion_task_id", sa.String(), nullable=True),
        sa.Column("status_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["repositories.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id", "commit_hash", name="uq_repo_commit_hash"),
    )
    op.create_index(
        op.f("ix_commit_details_celery_ingestion_task_id"),
        "commit_details",
        ["celery_ingestion_task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_commit_details_commit_hash"),
        "commit_details",
        ["commit_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_commit_details_id"), "commit_details", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_commit_details_ingestion_status"),
        "commit_details",
        ["ingestion_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_commit_details_repository_id"),
        "commit_details",
        ["repository_id"],
        unique=False,
    )

    # Create the commit_file_diffs table
    op.create_table(
        "commit_file_diffs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("commit_detail_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("change_type", file_change_type_enum, nullable=False),
        sa.Column("old_path", sa.String(), nullable=True),
        sa.Column("diff_text", sa.Text(), nullable=False),
        sa.Column("insertions", sa.Integer(), nullable=False),
        sa.Column("deletions", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["commit_detail_id"], ["commit_details.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_commit_file_diffs_commit_detail_id"),
        "commit_file_diffs",
        ["commit_detail_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_commit_file_diffs_id"), "commit_file_diffs", ["id"], unique=False
    )


def downgrade() -> None:
    """Reverts the changes made in the upgrade function."""
    # Drop tables first as they depend on the ENUM types
    op.drop_index(op.f("ix_commit_file_diffs_id"), table_name="commit_file_diffs")
    op.drop_index(
        op.f("ix_commit_file_diffs_commit_detail_id"), table_name="commit_file_diffs"
    )
    op.drop_table("commit_file_diffs")

    op.drop_index(op.f("ix_commit_details_repository_id"), table_name="commit_details")
    op.drop_index(
        op.f("ix_commit_details_ingestion_status"), table_name="commit_details"
    )
    op.drop_index(op.f("ix_commit_details_id"), table_name="commit_details")
    op.drop_index(op.f("ix_commit_details_commit_hash"), table_name="commit_details")
    op.drop_index(
        op.f("ix_commit_details_celery_ingestion_task_id"), table_name="commit_details"
    )
    op.drop_table("commit_details")

    # Now drop the ENUM types using the SQLAlchemy construct
    sa.Enum(name="file_change_type_enum").drop(op.get_bind())
    sa.Enum(name="commit_ingestion_status_enum").drop(op.get_bind())
