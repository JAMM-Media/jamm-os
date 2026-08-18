"""add_timezone_to_firm

Revision ID: b2321b6bb22a
Revises: 1ed5f6118514
Create Date: 2026-08-17 15:04:40.946953

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2321b6bb22a'
down_revision: Union[str, Sequence[str], None] = '1ed5f6118514'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'firms',
        sa.Column(
            'timezone',
            sa.String(length=100),
            server_default='America/New_York',
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('firms', 'timezone')
