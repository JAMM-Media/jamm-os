"""add task_id to time_entries

Revision ID: u1v2w3x4y5z6
Revises: t7u8v9w0x1y2
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'u1v2w3x4y5z6'
down_revision: Union[str, Sequence[str], None] = 't7u8v9w0x1y2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'time_entries',
        sa.Column('task_id', sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        op.f('fk_time_entries_task_id_tasks'),
        'time_entries', 'tasks',
        ['task_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        op.f('ix_time_entries_task_id'),
        'time_entries', ['task_id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_time_entries_task_id'), table_name='time_entries')
    op.drop_constraint(op.f('fk_time_entries_task_id_tasks'), 'time_entries', type_='foreignkey')
    op.drop_column('time_entries', 'task_id')
