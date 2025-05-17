"""setup_cascade_deletes_for_repository_and_children

Revision ID: 14d6524289d9
Revises: 3fa95af1143b
Create Date: 2025-05-17 08:56:22.547289

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
# We don't need postgresql dialect import here unless using specific PG types directly in op commands
# from sqlalchemy.dialects import postgresql 

# revision identifiers, used by Alembic.
revision: str = '14d6524289d9'
down_revision: Union[str, None] = '3fa95af1143b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add ON DELETE CASCADE to foreign keys."""
    # --- Foreign Keys pointing to repositories.id ---
    op.drop_constraint('bot_patterns_repository_id_fkey', 'bot_patterns', type_='foreignkey')
    op.create_foreign_key(
        'bot_patterns_repository_id_fkey', 'bot_patterns', 'repositories',
        ['repository_id'], ['id'], ondelete='CASCADE'
    )

    op.drop_constraint('datasets_repository_id_fkey', 'datasets', type_='foreignkey')
    op.create_foreign_key(
        'datasets_repository_id_fkey', 'datasets', 'repositories',
        ['repository_id'], ['id'], ondelete='CASCADE'
    )

    op.drop_constraint('github_issues_repository_id_fkey', 'github_issues', type_='foreignkey')
    op.create_foreign_key(
        'github_issues_repository_id_fkey', 'github_issues', 'repositories',
        ['repository_id'], ['id'], ondelete='CASCADE'
    )

    op.drop_constraint('ck_metrics_repository_id_fkey', 'ck_metrics', type_='foreignkey')
    op.create_foreign_key(
        'ck_metrics_repository_id_fkey', 'ck_metrics', 'repositories',
        ['repository_id'], ['id'], ondelete='CASCADE'
    )

    op.drop_constraint('commit_guru_metrics_repository_id_fkey', 'commit_guru_metrics', type_='foreignkey')
    op.create_foreign_key(
        'commit_guru_metrics_repository_id_fkey', 'commit_guru_metrics', 'repositories',
        ['repository_id'], ['id'], ondelete='CASCADE'
    )

    # --- Foreign Keys pointing to datasets.id ---
    op.drop_constraint('ml_models_dataset_id_fkey', 'ml_models', type_='foreignkey')
    op.create_foreign_key(
        'ml_models_dataset_id_fkey', 'ml_models', 'datasets',
        ['dataset_id'], ['id'], ondelete='CASCADE' # Changed from SET NULL to CASCADE
    )

    op.drop_constraint('training_jobs_dataset_id_fkey', 'training_jobs', type_='foreignkey')
    op.create_foreign_key(
        'training_jobs_dataset_id_fkey', 'training_jobs', 'datasets',
        ['dataset_id'], ['id'], ondelete='CASCADE'
    )

    op.drop_constraint('hp_search_jobs_dataset_id_fkey', 'hp_search_jobs', type_='foreignkey')
    op.create_foreign_key(
        'hp_search_jobs_dataset_id_fkey', 'hp_search_jobs', 'datasets',
        ['dataset_id'], ['id'], ondelete='CASCADE'
    )

    # --- Foreign Keys pointing to ml_models.id ---
    op.drop_constraint('inference_jobs_ml_model_id_fkey', 'inference_jobs', type_='foreignkey')
    op.create_foreign_key(
        'inference_jobs_ml_model_id_fkey', 'inference_jobs', 'ml_models',
        ['ml_model_id'], ['id'], ondelete='CASCADE'
    )

    # --- Foreign Keys pointing to inference_jobs.id ---
    op.drop_constraint('xai_results_inference_job_id_fkey', 'xai_results', type_='foreignkey')
    op.create_foreign_key(
        'xai_results_inference_job_id_fkey', 'xai_results', 'inference_jobs',
        ['inference_job_id'], ['id'], ondelete='CASCADE'
    )
    
    # --- Foreign Keys for commit_github_issue_association ---
    # This table links commit_guru_metrics and github_issues. 
    # If a commit_guru_metric is deleted (because its repository is deleted),
    # or a github_issue is deleted (because its repository is deleted),
    # the association rows should also be deleted.
    op.drop_constraint('commit_github_issue_association_commit_guru_metric_id_fkey', 'commit_github_issue_association', type_='foreignkey')
    op.create_foreign_key(
        'commit_github_issue_association_commit_guru_metric_id_fkey', 'commit_github_issue_association', 'commit_guru_metrics',
        ['commit_guru_metric_id'], ['id'], ondelete='CASCADE'
    )
    
    op.drop_constraint('commit_github_issue_association_github_issue_id_fkey', 'commit_github_issue_association', type_='foreignkey')
    op.create_foreign_key(
        'commit_github_issue_association_github_issue_id_fkey', 'commit_github_issue_association', 'github_issues',
        ['github_issue_id'], ['id'], ondelete='CASCADE'
    )

    # Note: ml_models also has FKs to training_jobs and hp_search_jobs.
    # Current DDL is ondelete='SET NULL'. If those jobs are deleted (e.g., if datasets are deleted),
    # the ml_model's FK fields will become NULL. This is usually fine.
    # If you wanted ml_models to be deleted if their originating job is deleted,
    # you'd change those FKs to CASCADE as well. For now, we'll leave them as SET NULL
    # as per the original schema, as the primary cascade path is Repo -> Dataset -> Job/Model.
    # op.drop_constraint('ml_models_training_job_id_fkey', 'ml_models', type_='foreignkey')
    # op.create_foreign_key(
    #     'ml_models_training_job_id_fkey', 'ml_models', 'training_jobs',
    #     ['training_job_id'], ['id'], ondelete='SET NULL' # Or CASCADE if desired
    # )
    # op.drop_constraint('ml_models_hp_search_job_id_fkey', 'ml_models', type_='foreignkey')
    # op.create_foreign_key(
    #     'ml_models_hp_search_job_id_fkey', 'ml_models', 'hp_search_jobs',
    #     ['hp_search_job_id'], ['id'], ondelete='SET NULL' # Or CASCADE if desired
    # )


def downgrade() -> None:
    """Downgrade schema to remove ON DELETE CASCADE from foreign keys."""
    # Revert foreign keys to their original state (typically no ON DELETE action or RESTRICT/NO ACTION by default)
    
    # --- Revert Foreign Keys for commit_github_issue_association ---
    op.drop_constraint('commit_github_issue_association_github_issue_id_fkey', 'commit_github_issue_association', type_='foreignkey')
    op.create_foreign_key(
        'commit_github_issue_association_github_issue_id_fkey', 'commit_github_issue_association', 'github_issues',
        ['github_issue_id'], ['id'], ondelete='CASCADE' # Original was CASCADE
    )
    op.drop_constraint('commit_github_issue_association_commit_guru_metric_id_fkey', 'commit_github_issue_association', type_='foreignkey')
    op.create_foreign_key(
        'commit_github_issue_association_commit_guru_metric_id_fkey', 'commit_github_issue_association', 'commit_guru_metrics',
        ['commit_guru_metric_id'], ['id'], ondelete='CASCADE' # Original was CASCADE
    )

    # --- Revert Foreign Keys pointing to inference_jobs.id ---
    op.drop_constraint('xai_results_inference_job_id_fkey', 'xai_results', type_='foreignkey')
    op.create_foreign_key(
        'xai_results_inference_job_id_fkey', 'xai_results', 'inference_jobs',
        ['inference_job_id'], ['id'], ondelete='CASCADE' # Original was CASCADE
    )

    # --- Revert Foreign Keys pointing to ml_models.id ---
    op.drop_constraint('inference_jobs_ml_model_id_fkey', 'inference_jobs', type_='foreignkey')
    op.create_foreign_key(
        'inference_jobs_ml_model_id_fkey', 'inference_jobs', 'ml_models',
        ['ml_model_id'], ['id'], ondelete='CASCADE' # Original was CASCADE
    )
    
    # --- Revert Foreign Keys pointing to datasets.id ---
    op.drop_constraint('hp_search_jobs_dataset_id_fkey', 'hp_search_jobs', type_='foreignkey')
    op.create_foreign_key(
        'hp_search_jobs_dataset_id_fkey', 'hp_search_jobs', 'datasets',
        ['dataset_id'], ['id'], ondelete='CASCADE' # Original was CASCADE
    )

    op.drop_constraint('training_jobs_dataset_id_fkey', 'training_jobs', type_='foreignkey')
    op.create_foreign_key(
        'training_jobs_dataset_id_fkey', 'training_jobs', 'datasets',
        ['dataset_id'], ['id'], ondelete='CASCADE' # Original was CASCADE
    )

    op.drop_constraint('ml_models_dataset_id_fkey', 'ml_models', type_='foreignkey')
    op.create_foreign_key(
        'ml_models_dataset_id_fkey', 'ml_models', 'datasets',
        ['dataset_id'], ['id'], ondelete='SET NULL' # Original was SET NULL for this one
    )

    # --- Revert Foreign Keys pointing to repositories.id ---
    op.drop_constraint('commit_guru_metrics_repository_id_fkey', 'commit_guru_metrics', type_='foreignkey')
    op.create_foreign_key(
        'commit_guru_metrics_repository_id_fkey', 'commit_guru_metrics', 'repositories',
        ['repository_id'], ['id'] # Default ON DELETE (NO ACTION / RESTRICT)
    )

    op.drop_constraint('ck_metrics_repository_id_fkey', 'ck_metrics', type_='foreignkey')
    op.create_foreign_key(
        'ck_metrics_repository_id_fkey', 'ck_metrics', 'repositories',
        ['repository_id'], ['id']
    )

    op.drop_constraint('github_issues_repository_id_fkey', 'github_issues', type_='foreignkey')
    op.create_foreign_key(
        'github_issues_repository_id_fkey', 'github_issues', 'repositories',
        ['repository_id'], ['id'], ondelete='CASCADE' # Original was CASCADE for this one
    )

    op.drop_constraint('datasets_repository_id_fkey', 'datasets', type_='foreignkey')
    op.create_foreign_key(
        'datasets_repository_id_fkey', 'datasets', 'repositories',
        ['repository_id'], ['id'], ondelete='CASCADE' # Original was CASCADE for this one
    )

    op.drop_constraint('bot_patterns_repository_id_fkey', 'bot_patterns', type_='foreignkey')
    op.create_foreign_key(
        'bot_patterns_repository_id_fkey', 'bot_patterns', 'repositories',
        ['repository_id'], ['id'], ondelete='CASCADE' # Original was CASCADE for this one
    )

    # The ml_models FKs to training_jobs and hp_search_jobs were SET NULL, so they remain SET NULL
    # op.drop_constraint('ml_models_hp_search_job_id_fkey', 'ml_models', type_='foreignkey')
    # op.create_foreign_key(
    #     'ml_models_hp_search_job_id_fkey', 'ml_models', 'hp_search_jobs',
    #     ['hp_search_job_id'], ['id'], ondelete='SET NULL'
    # )
    # op.drop_constraint('ml_models_training_job_id_fkey', 'ml_models', type_='foreignkey')
    # op.create_foreign_key(
    #     'ml_models_training_job_id_fkey', 'ml_models', 'training_jobs',
    #     ['training_job_id'], ['id'], ondelete='SET NULL'
    # )