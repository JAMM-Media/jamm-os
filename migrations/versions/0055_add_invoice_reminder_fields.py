# migrations/versions/0055_add_invoice_reminder_fields.py

"""add invoice reminder fields

Revision ID: 0055_add_invoice_reminder_fields
Revises: 5ed2eed1ea77
Create Date: 2026-06-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0055_add_invoice_reminder_fields'
down_revision: Union[str, Sequence[str], None] = '5ed2eed1ea77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'invoices',
        sa.Column('reminder_count', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'invoices',
        sa.Column('last_reminder_sent_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('invoices', 'last_reminder_sent_at')
    op.drop_column('invoices', 'reminder_count')
