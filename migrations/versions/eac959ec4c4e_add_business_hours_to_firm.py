# migrations/versions/eac959ec4c4e_add_business_hours_to_firm.py
"""add business hours to firm

Adds business_hours_start and business_hours_end to the firms table.
Both are 24h hour values (0-23); defaults are 8 and 18 (8am-6pm),
matching contract section 6.1's stated default send window.

Revision ID: eac959ec4c4e
Revises: 291581aa9ba0
Create Date: 2026-08-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'eac959ec4c4e'
down_revision: Union[str, Sequence[str], None] = '291581aa9ba0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'firms',
        sa.Column(
            'business_hours_start',
            sa.Integer(),
            server_default='8',
            nullable=False,
        ),
    )
    op.add_column(
        'firms',
        sa.Column(
            'business_hours_end',
            sa.Integer(),
            server_default='18',
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('firms', 'business_hours_end')
    op.drop_column('firms', 'business_hours_start')
