"""add_num_rows_to_dataset_table

Revision ID: 4e7be0333031
Revises: 14d6524289d9
Create Date: 2025-05-18 18:08:37.760960

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e7be0333031'
down_revision: Union[str, None] = '14d6524289d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('datasets', sa.Column('num_rows', sa.Integer(), nullable=True, comment="Number of rows in the generated dataset"))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('datasets', 'num_rows')
