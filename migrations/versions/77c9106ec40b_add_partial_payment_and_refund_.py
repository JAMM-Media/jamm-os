# migrations/versions/77c9106ec40b_add_partial_payment_and_refund_.py

"""add partial payment and refund tracking to invoices

Revision ID: 77c9106ec40b
Revises: e06c341c7b5a
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '77c9106ec40b'
down_revision: Union[str, Sequence[str], None] = 'e06c341c7b5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE invoicestatus ADD VALUE IF NOT EXISTS 'partial'")
    op.execute("ALTER TYPE invoicestatus ADD VALUE IF NOT EXISTS 'refunded'")

    op.add_column(
        'invoices',
        sa.Column('amount_paid', sa.Numeric(10, 2), nullable=False, server_default='0'),
    )
    op.add_column(
        'invoices',
        sa.Column('refunded_amount', sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        'invoices',
        sa.Column('refund_reason', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('invoices', 'refund_reason')
    op.drop_column('invoices', 'refunded_amount')
    op.drop_column('invoices', 'amount_paid')

    # Postgres cannot drop individual enum values; the 'partial' and
    # 'refunded' members are left in place on downgrade.
