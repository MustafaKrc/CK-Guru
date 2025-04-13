"""Seed default global bot patterns

Revision ID: e39d1ab0a19f # Populated by Alembic
Revises: aab1c05d7332 # Populated by Alembic
Create Date: <timestamp> # Populated by Alembic

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

# revision identifiers, used by Alembic.
revision: str = 'e39d1ab0a19f'
down_revision: Union[str, None] = 'aab1c05d7332'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define table structure for insertion (safer than importing model directly in migrations)
bot_patterns_table = sa.table(
    'bot_patterns',
    sa.column('id', sa.Integer),
    sa.column('repository_id', sa.Integer), # Will be NULL for global
    sa.column('pattern', sa.String),
    sa.column('pattern_type', ENUM('REGEX', 'WILDCARD', 'EXACT', name='pattern_type_enum')),  # Use ENUM instead of String
    sa.column('is_exclusion', sa.Boolean),
    sa.column('description', sa.Text)
)

# List of default global bot patterns to seed
# Use uppercase enum values that match the database enum definition
default_patterns = [
    {
        'repository_id': None, 'pattern': 'dependabot[bot]', 'pattern_type': 'EXACT',
        'is_exclusion': False, 'description': 'GitHub Dependabot'
    },
    {
        'repository_id': None, 'pattern': 'dependabot-preview[bot]', 'pattern_type': 'EXACT',
        'is_exclusion': False, 'description': 'GitHub Dependabot Preview'
    },
    {
        'repository_id': None, 'pattern': 'github-actions[bot]', 'pattern_type': 'EXACT',
        'is_exclusion': False, 'description': 'GitHub Actions Bot'
    },
    {
        'repository_id': None, 'pattern': 'renovate[bot]', 'pattern_type': 'EXACT',
        'is_exclusion': False, 'description': 'Renovate Bot'
    },
    {
        'repository_id': None, 'pattern': 'snyk-bot', 'pattern_type': 'EXACT',
        'is_exclusion': False, 'description': 'Snyk Bot'
    },
    # Add more known common bots here if desired
    # Example using regex (use cautiously):
    {
        'repository_id': None, 'pattern': r'.*\[bot\]$', 'pattern_type': 'REGEX',
        'is_exclusion': False, 'description': 'Generic pattern for names ending in [bot]'
    },
]


def upgrade() -> None:
    """Seed default global bot patterns."""
    print("Seeding default global bot patterns...")
    try:
        op.bulk_insert(bot_patterns_table, default_patterns)
        print(f"Successfully inserted {len(default_patterns)} default global bot patterns.")
    except Exception as e:
        print(f"Error seeding default bot patterns: {e}")
        # Decide if failure should halt migration (raise) or just warn
        # raise e # Uncomment to make seeding failure stop the migration


def downgrade() -> None:
    """Remove the seeded default global bot patterns."""
    print("Removing default global bot patterns...")
    try:
        # Construct WHERE clause to delete only the seeded patterns
        # Be careful if users might have created patterns with the exact same strings
        pattern_strings = [p['pattern'] for p in default_patterns]
        pattern_types = [p['pattern_type'] for p in default_patterns] # Could refine if types differ

        # Delete global patterns matching the seeded strings and types
        op.execute(
            bot_patterns_table.delete().where(
                sa.and_(
                    bot_patterns_table.c.repository_id.is_(None),
                    bot_patterns_table.c.pattern.in_(pattern_strings),
                    bot_patterns_table.c.pattern_type.in_(pattern_types), # Match type too
                    bot_patterns_table.c.is_exclusion == False # Match exclusion flag
                )
            )
        )
        print(f"Attempted removal of seeded global bot patterns matching: {pattern_strings}")
    except Exception as e:
        print(f"Error removing default bot patterns during downgrade: {e}")
        # raise e # Uncomment if downgrade failure should stop migration