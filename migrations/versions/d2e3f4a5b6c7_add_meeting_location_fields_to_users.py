# migrations/versions/d2e3f4a5b6c7_add_meeting_location_fields_to_users.py

"""add meeting location fields to users

Revision ID: d2e3f4a5b6c7
Revises: c4d5e6f7a8b9
Create Date: 2026-08-15

Adds per-staff meeting location setting to users, per section 7.2.
meeting_location_type: one of video, phone, office (VARCHAR, native_enum=False).
meeting_location_value: the URL, phone number, or address as a free-form string.

Both nullable -- null means the staff member has not configured a meeting location yet.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column(
            'meeting_location_type',
            sa.Enum('video', 'phone', 'office', name='meetinglocationtype', native_enum=False),
            nullable=True,
        ),
    )
    op.add_column(
        'users',
        sa.Column('meeting_location_value', sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'meeting_location_value')
    op.drop_column('users', 'meeting_location_type')
