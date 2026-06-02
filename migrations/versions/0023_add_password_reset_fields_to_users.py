"""add_password_reset_fields_to_users

Revision ID: 0023_add_password_reset_fields_to_users
Revises: 0022_add_behavioral_events_table
Create Date: 2026-04-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0023_add_password_reset_fields_to_users'
down_revision: Union[str, Sequence[str], None] = '0022_add_behavioral_events_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column(
        'password_reset_token_hash',
        sa.String(length=64),
        nullable=True,
    ))
    op.add_column('users', sa.Column(
        'password_reset_expires_at',
        sa.DateTime(timezone=True),
        nullable=True,
    ))


def downgrade() -> None:
    op.drop_column('users', 'password_reset_expires_at')
    op.drop_column('users', 'password_reset_token_hash')
