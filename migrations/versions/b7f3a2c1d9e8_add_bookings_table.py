# migrations/versions/b7f3a2c1d9e8_add_bookings_table.py

"""add bookings table

Revision ID: b7f3a2c1d9e8
Revises: 3875bfc20b03
Create Date: 2026-08-14

One row per scheduled meeting with a lead, per section 7.2 and 9.1.
No slot-computation logic or booking endpoints in this revision -- data
model foundation only.

BookingStatus stored as VARCHAR (native_enum=False) per standing rules.
lead_id and staff_user_id both use SET NULL so booking history survives
lead deletion or staff turnover.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7f3a2c1d9e8'
down_revision: Union[str, Sequence[str], None] = '3875bfc20b03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'bookings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('lead_id', sa.Uuid(), nullable=True),
        sa.Column('staff_user_id', sa.Uuid(), nullable=True),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            'status',
            sa.Enum(
                'scheduled', 'completed', 'no_show', 'canceled', 'rescheduled',
                name='bookingstatus',
                native_enum=False,
            ),
            server_default='scheduled',
            nullable=False,
        ),
        sa.Column('location_snapshot', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['staff_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_bookings_firm_id', 'bookings', ['firm_id'], unique=False)
    op.create_index('ix_bookings_lead_id', 'bookings', ['lead_id'], unique=False)
    op.create_index('ix_bookings_staff_user_id', 'bookings', ['staff_user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_bookings_staff_user_id', table_name='bookings')
    op.drop_index('ix_bookings_lead_id', table_name='bookings')
    op.drop_index('ix_bookings_firm_id', table_name='bookings')
    op.drop_table('bookings')
