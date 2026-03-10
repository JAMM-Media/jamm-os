# migrations/versions/0003_rename_projects_to_engagements.py

"""rename projects to engagements

Revision ID: 0003
Revises: 9fbb6c128525
Create Date: 2026-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision: str = '0003'
down_revision: Union[str, None] = '9fbb6c128525'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Rename the projects table to engagements
    op.rename_table('projects', 'engagements')

    # Step 2: Rename project_id column on tasks to engagement_id
    op.alter_column(
        'tasks',
        'project_id',
        new_column_name='engagement_id',
    )

    # Step 3: Drop the old foreign key constraint pointing to projects
    op.drop_constraint(
        'tasks_project_id_fkey',
        'tasks',
        type_='foreignkey',
    )

    # Step 4: Create new foreign key constraint pointing to engagements
    op.create_foreign_key(
        'tasks_engagement_id_fkey',
        'tasks',
        'engagements',
        ['engagement_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint(
        'tasks_engagement_id_fkey',
        'tasks',
        type_='foreignkey',
    )

    op.alter_column(
        'tasks',
        'engagement_id',
        new_column_name='project_id',
    )

    op.create_foreign_key(
        'tasks_project_id_fkey',
        'tasks',
        'projects',
        ['project_id'],
        ['id'],
        ondelete='CASCADE',
    )

    op.rename_table('engagements', 'projects')