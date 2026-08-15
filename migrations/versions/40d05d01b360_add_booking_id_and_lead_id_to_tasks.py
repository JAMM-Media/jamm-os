"""add booking_id and lead_id to tasks

Revision ID: 40d05d01b360
Revises: d2e3f4a5b6c7
Create Date: 2026-08-15 12:23:09.027267

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '40d05d01b360'
down_revision: Union[str, Sequence[str], None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('booking_id', sa.Uuid(), nullable=True))
    op.add_column('tasks', sa.Column('lead_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_tasks_booking_id'), 'tasks', ['booking_id'], unique=False)
    op.create_index(op.f('ix_tasks_lead_id'), 'tasks', ['lead_id'], unique=False)
    op.create_foreign_key(
        'fk_tasks_booking_id',
        'tasks', 'bookings',
        ['booking_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_tasks_lead_id',
        'tasks', 'leads',
        ['lead_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_tasks_lead_id', 'tasks', type_='foreignkey')
    op.drop_constraint('fk_tasks_booking_id', 'tasks', type_='foreignkey')
    op.drop_index(op.f('ix_tasks_lead_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_booking_id'), table_name='tasks')
    op.drop_column('tasks', 'lead_id')
    op.drop_column('tasks', 'booking_id')
