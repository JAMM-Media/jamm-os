# migrations/versions/0004_add_2fa_fields_to_users.py

"""add 2fa fields to users

Revision ID: 0004
Revises: 0003
Create Date: 2026-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add totp_secret — stores the 2FA secret key, nullable until user enables 2FA
    op.add_column(
        'users',
        sa.Column('totp_secret', sa.String(), nullable=True),
    )

    # Add totp_enabled — whether 2FA is active for this user
    op.add_column(
        'users',
        sa.Column('totp_enabled', sa.Boolean(), nullable=False, server_default='false'),
    )

    # Add backup_codes — stored as JSON string, nullable until 2FA is enabled
    op.add_column(
        'users',
        sa.Column('backup_codes', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'backup_codes')
    op.drop_column('users', 'totp_enabled')
    op.drop_column('users', 'totp_secret')