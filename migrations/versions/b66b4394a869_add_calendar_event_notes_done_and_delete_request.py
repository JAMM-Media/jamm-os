# migrations/versions/b66b4394a869_add_calendar_event_notes_done_and_delete_request.py
"""add calendar event notes done and delete request

Revision ID: b66b4394a869
Revises: 0310a1b5d296
Create Date: 2026-10-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b66b4394a869'
down_revision: Union[str, Sequence[str], None] = '0310a1b5d296'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'calendar_events',
        sa.Column('staff_notes', sa.Text(), nullable=True),
    )
    op.add_column(
        'calendar_events',
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'calendar_events',
        sa.Column('delete_requested_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'calendar_events',
        sa.Column('delete_requested_by', sa.Uuid(), nullable=True),
    )
    op.add_column(
        'calendar_events',
        sa.Column('delete_request_reason', sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        'fk_calendar_events_delete_requested_by_users',
        'calendar_events', 'users',
        ['delete_requested_by'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_calendar_events_delete_requested_by_users',
        'calendar_events',
        type_='foreignkey',
    )
    op.drop_column('calendar_events', 'delete_request_reason')
    op.drop_column('calendar_events', 'delete_requested_by')
    op.drop_column('calendar_events', 'delete_requested_at')
    op.drop_column('calendar_events', 'completed_at')
    op.drop_column('calendar_events', 'staff_notes')
