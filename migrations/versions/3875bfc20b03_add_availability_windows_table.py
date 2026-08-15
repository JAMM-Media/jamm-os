# migrations/versions/3875bfc20b03_add_availability_windows_table.py

"""add availability_windows table

Revision ID: 3875bfc20b03
Revises: de2c76e703db
Create Date: 2026-08-14

Per-staff weekly availability windows for native booking (section 7.2).
One row per staff member per day of week. No endpoints or booking logic
in this revision -- data model foundation only.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3875bfc20b03'
down_revision: Union[str, Sequence[str], None] = 'de2c76e703db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'availability_windows',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('buffer_before_minutes', sa.Integer(), server_default='0', nullable=False),
        sa.Column('buffer_after_minutes', sa.Integer(), server_default='0', nullable=False),
        sa.Column('meeting_duration_minutes', sa.Integer(), nullable=False),
        sa.Column('daily_cap', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'day_of_week', name='uq_availability_window_user_day'),
    )
    op.create_index('ix_availability_windows_firm_id', 'availability_windows', ['firm_id'], unique=False)
    op.create_index('ix_availability_windows_user_id', 'availability_windows', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_availability_windows_user_id', table_name='availability_windows')
    op.drop_index('ix_availability_windows_firm_id', table_name='availability_windows')
    op.drop_table('availability_windows')
