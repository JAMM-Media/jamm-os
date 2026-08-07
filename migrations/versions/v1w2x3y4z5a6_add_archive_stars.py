"""add archive_stars

Revision ID: v1w2x3y4z5a6
Revises: u1v2w3x4y5z6
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'v1w2x3y4z5a6'
down_revision: Union[str, Sequence[str], None] = 'u1v2w3x4y5z6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'archive_stars',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('task_id', sa.Uuid(), nullable=False),
        sa.Column('starred_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'task_id', name='uq_archive_stars_user_task'),
    )
    op.create_index(op.f('ix_archive_stars_user_id'), 'archive_stars', ['user_id'], unique=False)
    op.create_index(op.f('ix_archive_stars_task_id'), 'archive_stars', ['task_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_archive_stars_task_id'), table_name='archive_stars')
    op.drop_index(op.f('ix_archive_stars_user_id'), table_name='archive_stars')
    op.drop_table('archive_stars')
