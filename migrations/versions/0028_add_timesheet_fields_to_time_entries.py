"""add timesheet fields to time_entries

Revision ID: 0028_add_timesheet_fields_to_time_entries
Revises: 0027_add_attachment_fields_to_firm_messages
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0028_add_timesheet_fields_to_time_entries'
down_revision: Union[str, Sequence[str], None] = '0027_add_attachment_fields_to_firm_messages'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('time_entries', sa.Column('start_time', sa.Time(), nullable=True))
    op.add_column('time_entries', sa.Column('end_time', sa.Time(), nullable=True))
    op.add_column('time_entries', sa.Column('activity_type', sa.String(length=100), nullable=True))
    op.add_column('time_entries', sa.Column('is_submitted', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('time_entries', sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('time_entries', sa.Column('is_approved', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('time_entries', sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('time_entries', sa.Column('approved_by_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_time_entries_approved_by_id',
        'time_entries', 'users',
        ['approved_by_id'], ['id'],
        ondelete='SET NULL',
    )
    op.add_column('time_entries', sa.Column('edited_after_submission', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('time_entries', sa.Column('edit_note', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_constraint('fk_time_entries_approved_by_id', 'time_entries', type_='foreignkey')
    op.drop_column('time_entries', 'edit_note')
    op.drop_column('time_entries', 'edited_after_submission')
    op.drop_column('time_entries', 'approved_by_id')
    op.drop_column('time_entries', 'approved_at')
    op.drop_column('time_entries', 'is_approved')
    op.drop_column('time_entries', 'submitted_at')
    op.drop_column('time_entries', 'is_submitted')
    op.drop_column('time_entries', 'activity_type')
    op.drop_column('time_entries', 'end_time')
    op.drop_column('time_entries', 'start_time')
