# migrations/versions/c3a8c478ba34_add_is_pinned_to_portal_notifications.py
"""add is_pinned to portal_notifications

Supports the pinned attribution survey notification (Contract section 4.1):
pinned notifications survive mark-all-read and cannot be individually
marked read -- they clear only on explicit completion.

Revision ID: c3a8c478ba34
Revises: eac959ec4c4e
Create Date: 2026-08-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3a8c478ba34'
down_revision: Union[str, Sequence[str], None] = 'eac959ec4c4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'portal_notifications',
        sa.Column(
            'is_pinned',
            sa.Boolean(),
            server_default='false',
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('portal_notifications', 'is_pinned')
