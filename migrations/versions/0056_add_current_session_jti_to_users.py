# migrations/versions/0056_add_current_session_jti_to_users.py

"""add current_session_jti to users

Revision ID: 0056_add_current_session_jti_to_users
Revises: 0055_add_invoice_reminder_fields
Create Date: 2026-06-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0056_add_current_session_jti_to_users'
down_revision: Union[str, Sequence[str], None] = '0055_add_invoice_reminder_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('current_session_jti', sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'current_session_jti')
