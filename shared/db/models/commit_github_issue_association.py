# shared/db/models/commit_github_issue_association.py
from sqlalchemy import Table, Column, Integer, ForeignKey, PrimaryKeyConstraint
from shared.db.base_class import Base # Needed for metadata

# Define the association table explicitly using SQLAlchemy Core Table construct
# It links commit_guru_metrics and github_issues
commit_github_issue_association_table = Table(
    'commit_github_issue_association',
    Base.metadata, # Associate with the Base metadata
    Column(
        'commit_guru_metric_id',
        Integer,
        # Ensure cascade settings match your requirements
        ForeignKey('commit_guru_metrics.id', ondelete='CASCADE'),
        primary_key=True # Part of composite primary key
    ),
    Column(
        'github_issue_id',
        Integer,
        ForeignKey('github_issues.id', ondelete='CASCADE'),
        primary_key=True # Part of composite primary key
    )
    # No extra columns needed for a simple many-to-many link
)

# We don't define an ORM class for this table, SQLAlchemy handles it
# based on the `secondary` argument in the relationship definitions.