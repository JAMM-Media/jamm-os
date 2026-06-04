"""auth_overhaul_staff_policy_and_magic_links

Revision ID: 0024_auth_overhaul
Revises: 0023_add_password_reset_fields_to_users
Create Date: 2026-04-27

Adds:
- firms.staff_auth_policy  (varchar NOT NULL DEFAULT 'either')
- users.magic_link_token_hash  (varchar(128) nullable)
- users.magic_link_expires_at  (timestamptz nullable)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0024_auth_overhaul'
down_revision: Union[str, Sequence[str], None] = '0023_add_password_reset_fields_to_users'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('firms', sa.Column(
        'staff_auth_policy',
        sa.String(),
        nullable=False,
        server_default='either',
    ))

    op.add_column('users', sa.Column(
        'magic_link_token_hash',
        sa.String(length=128),
        nullable=True,
    ))
    op.add_column('users', sa.Column(
        'magic_link_expires_at',
        sa.DateTime(timezone=True),
        nullable=True,
    ))


def downgrade() -> None:
    op.drop_column('users', 'magic_link_expires_at')
    op.drop_column('users', 'magic_link_token_hash')
    op.drop_column('firms', 'staff_auth_policy')
