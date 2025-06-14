"""add_ml_model_type_definitions_table

Revision ID: d9a14200cce1
Revises: 4e7be0333031
Create Date: 2025-05-27 17:36:23.433052

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d9a14200cce1"
down_revision: Union[str, None] = "4e7be0333031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ml_model_type_definitions",
        sa.Column(
            "type_name",
            sa.String(),
            nullable=False,
            primary_key=True,
            comment="Internal name, e.g., from ModelTypeEnum",
        ),
        sa.Column(
            "display_name",
            sa.String(),
            nullable=False,
            comment="User-friendly display name",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Description of the model type",
        ),
        sa.Column(
            "hyperparameter_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Schema defining configurable hyperparameters",
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="If this model type is available for selection",
        ),
        sa.Column(
            "last_updated_by",
            sa.String(),
            nullable=True,
            comment="Identifier of the worker/process that last updated this record",
        ),
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
            onupdate=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("type_name"),
    )
    op.create_index(
        op.f("ix_ml_model_type_definitions_type_name"),
        "ml_model_type_definitions",
        ["type_name"],
        unique=False,
    )  # Index on PK is often implicit
    op.create_index(
        op.f("ix_ml_model_type_definitions_is_enabled"),
        "ml_model_type_definitions",
        ["is_enabled"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_ml_model_type_definitions_is_enabled"),
        table_name="ml_model_type_definitions",
    )
    op.drop_index(
        op.f("ix_ml_model_type_definitions_type_name"),
        table_name="ml_model_type_definitions",
    )
    op.drop_table("ml_model_type_definitions")
