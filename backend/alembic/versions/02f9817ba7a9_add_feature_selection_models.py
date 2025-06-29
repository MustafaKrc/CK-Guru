"""add_feature_selection_models

Revision ID: 02f9817ba7a9
Revises: 1d6a6db9e34b
Create Date: 2025-06-08 10:34:32.433104

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "02f9817ba7a9"
down_revision: Union[str, None] = "1d6a6db9e34b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "feature_selection_definitions",
        sa.Column(
            "name",
            sa.String(),
            nullable=False,
            comment="Unique identifier name, e.g., 'cbfs'",
        ),
        sa.Column(
            "display_name",
            sa.String(),
            nullable=False,
            comment="User-friendly name for the UI",
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column(
            "is_implemented",
            sa.Boolean(),
            nullable=False,
            comment="Is the algorithm implemented and available in any worker?",
        ),
        sa.Column(
            "last_updated_by",
            sa.String(),
            nullable=True,
            comment="Identifier of the worker that last synced this record",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_index(
        op.f("ix_feature_selection_definitions_is_implemented"),
        "feature_selection_definitions",
        ["is_implemented"],
        unique=False,
    )

    op.add_column(
        "datasets",
        sa.Column(
            "feature_selection_config",
            sa.JSON(),
            nullable=True,
            comment="Configuration for the feature selection algorithm, e.g., {'name': 'mrmr', 'params': {'k': 20}}",
        ),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("datasets", "feature_selection_config")
    op.drop_index(
        op.f("ix_feature_selection_definitions_is_implemented"),
        table_name="feature_selection_definitions",
    )
    op.drop_table("feature_selection_definitions")
    # ### end Alembic commands ###
