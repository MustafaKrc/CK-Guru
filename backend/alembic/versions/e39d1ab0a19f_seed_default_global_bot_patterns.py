"""Seed default global bot patterns

Revision ID: e39d1ab0a19f # Populated by Alembic
Revises: aab1c05d7332 # Populated by Alembic
Create Date: <timestamp> # Populated by Alembic

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM

# revision identifiers, used by Alembic.
revision: str = "e39d1ab0a19f"
down_revision: Union[str, None] = "aab1c05d7332"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define table structure for insertion (safer than importing model directly in migrations)
bot_patterns_table = sa.table(
    "bot_patterns",
    sa.column("id", sa.Integer),
    sa.column("repository_id", sa.Integer),  # Will be NULL for global
    sa.column("pattern", sa.String),
    sa.column(
        "pattern_type", ENUM("REGEX", "WILDCARD", "EXACT", name="pattern_type_enum")
    ),  # Use ENUM instead of String
    sa.column("is_exclusion", sa.Boolean),
    sa.column("description", sa.Text),
)

# List of default global bot patterns to seed
# Use uppercase enum values that match the database enum definition
default_patterns = []


def upgrade() -> None:
    """Seed default global bot patterns."""
    print("Seeding default global bot patterns...")
    try:
        op.bulk_insert(bot_patterns_table, default_patterns)
        print(
            f"Successfully inserted {len(default_patterns)} default global bot patterns."
        )
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
        pattern_strings = [p["pattern"] for p in default_patterns]
        pattern_types = [
            p["pattern_type"] for p in default_patterns
        ]  # Could refine if types differ

        # Delete global patterns matching the seeded strings and types
        op.execute(
            bot_patterns_table.delete().where(
                sa.and_(
                    bot_patterns_table.c.repository_id.is_(None),
                    bot_patterns_table.c.pattern.in_(pattern_strings),
                    bot_patterns_table.c.pattern_type.in_(
                        pattern_types
                    ),  # Match type too
                    not bot_patterns_table.c.is_exclusion,  # Match exclusion flag
                )
            )
        )
        print(
            f"Attempted removal of seeded global bot patterns matching: {pattern_strings}"
        )
    except Exception as e:
        print(f"Error removing default bot patterns during downgrade: {e}")
        # raise e # Uncomment if downgrade failure should stop migration
