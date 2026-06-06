# migrations/versions/0043_user_login_lockout_fields.py

"""0043_user_login_lockout_fields

Revision ID: 0043_user_login_lockout_fields
Revises: a72f5a2701c1
Create Date: 2026-06-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0043_user_login_lockout_fields'
down_revision: Union[str, Sequence[str], None] = 'a72f5a2701c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column(
            'failed_login_count',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
    )
    op.add_column(
        'users',
        sa.Column(
            'locked_until',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_count')
