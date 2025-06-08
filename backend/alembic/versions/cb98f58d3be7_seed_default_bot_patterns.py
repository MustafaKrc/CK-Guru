"""seed_default_bot_patterns

Revision ID: cb98f58d3be7
Revises: 4d08f6187d5b
Create Date: 2025-06-08 15:22:15.550879

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'cb98f58d3be7'
down_revision: Union[str, None] = '4d08f6187d5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


bot_patterns_table = sa.table(
    "bot_patterns",
    sa.column("pattern", sa.String),
    sa.column("is_exclusion", sa.Boolean),
    sa.column("description", sa.Text),
    sa.column("repository_id", sa.Integer)
)

default_patterns = [
    {'pattern': r'dependabot\[bot\]', 'is_exclusion': False, 'description': 'GitHub Dependabot service account.'},
    {'pattern': r'renovate\[bot\]', 'is_exclusion': False, 'description': 'Renovate Bot for dependency updates.'},
    {'pattern': r'.*\[bot\].*', 'is_exclusion': False, 'description': "Generic pattern for author names containing '[bot]'."},
    {'pattern': r'.*-bot$', 'is_exclusion': False, 'description': 'Generic pattern for author names ending with -bot.'},
    {'pattern': r'^bot-.*', 'is_exclusion': False, 'description': 'Generic pattern for author names starting with bot-.'},
    {'pattern': r'github-actions\[bot\]', 'is_exclusion': False, 'description': 'Commits made by GitHub Actions.'},
    {'pattern': r'snyk-bot', 'is_exclusion': False, 'description': 'Snyk security bot.'},
]

def upgrade() -> None:
    op.bulk_insert(bot_patterns_table, default_patterns)


def downgrade() -> None:
    # This will delete ALL global patterns, including any manually added ones.
    # A more precise downgrade would only delete the specific patterns from the list.
    op.execute(
        bot_patterns_table.delete().where(
            bot_patterns_table.c.repository_id.is_(None)
        )
    )