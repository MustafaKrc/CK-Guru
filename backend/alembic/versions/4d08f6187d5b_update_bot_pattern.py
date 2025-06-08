"""update_bot_pattern

Revision ID: 4d08f6187d5b
Revises: 02f9817ba7a9
Create Date: 2025-06-08 14:55:10.361762

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4d08f6187d5b'
down_revision: Union[str, None] = '02f9817ba7a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Simplifies the bot_patterns table by removing the pattern_type column
    and updating the unique constraint to only consider the pattern string.
    """
    print("Simplifying bot_patterns table to use regex only...")
    
    # --- Step 1: Drop the old, complex unique constraint ---
    # This constraint included 'pattern_type', which we are removing.
    # It must be dropped before the column can be dropped.
    op.drop_constraint('uq_repo_bot_pattern', 'bot_patterns', type_='unique')
    print("Dropped old unique constraint 'uq_repo_bot_pattern'.")

    # --- Step 2: Drop the 'pattern_type' column ---
    op.drop_column('bot_patterns', 'pattern_type')
    print("Dropped 'pattern_type' column.")

    # --- Step 3: Drop the associated ENUM type from PostgreSQL ---
    # This is a clean-up step to remove the now-unused 'pattern_type_enum' type from the DB.
    pattern_type_enum = postgresql.ENUM('REGEX', 'WILDCARD', 'EXACT', name='pattern_type_enum')
    pattern_type_enum.drop(op.get_bind())
    print("Dropped ENUM type 'pattern_type_enum'.")

    # --- Step 4: Create the new, simpler unique constraint ---
    # This new constraint ensures a pattern string is unique per repository (or globally).
    # We reuse the name for simplicity.
    op.create_unique_constraint(
        'uq_repo_bot_pattern', 'bot_patterns', ['repository_id', 'pattern']
    )
    print("Created new unique constraint on (repository_id, pattern).")
    
    print("Bot patterns simplification complete.")


def downgrade() -> None:
    """
    Reverts the bot_patterns table back to its original state with a pattern_type column.
    NOTE: Data for the original pattern types is lost; all restored patterns will be of type 'REGEX'.
    """
    print("Reverting bot_patterns table to include pattern types...")

    # --- Step 1: Drop the new, simpler unique constraint ---
    op.drop_constraint('uq_repo_bot_pattern', 'bot_patterns', type_='unique')
    print("Dropped new unique constraint.")

    # --- Step 2: Re-create the ENUM type in the database ---
    pattern_type_enum = postgresql.ENUM('REGEX', 'WILDCARD', 'EXACT', name='pattern_type_enum', create_type=False)
    pattern_type_enum.create(op.get_bind())
    print("Re-created ENUM type 'pattern_type_enum'.")

    # --- Step 3: Add the 'pattern_type' column back ---
    # We set a server_default of 'REGEX' to populate existing rows, as we can't know their original type.
    op.add_column(
        'bot_patterns', 
        sa.Column(
            'pattern_type',
            pattern_type_enum,
            nullable=False,
            server_default='REGEX'
        )
    )
    print("Added 'pattern_type' column back with default 'REGEX'.")
    
    # It's good practice to remove the server default after the initial population
    op.alter_column('bot_patterns', 'pattern_type', server_default=None)
    print("Removed server default from 'pattern_type' column.")

    # --- Step 4: Re-create the original, complex unique constraint ---
    op.create_unique_constraint(
        'uq_repo_bot_pattern',
        'bot_patterns',
        ['repository_id', 'pattern', 'pattern_type', 'is_exclusion']
    )
    print("Re-created original unique constraint.")
    
    print("Bot patterns table reversion complete.")