"""add unique constraint on invoice firm_id invoice_number

Revision ID: 0308036ee038
Revises: 77c9106ec40b
Create Date: 2026-07-03 11:48:04.281545

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0308036ee038'
down_revision: Union[str, Sequence[str], None] = '77c9106ec40b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint('uq_invoice_firm_invoice_number', 'invoices', ['firm_id', 'invoice_number'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_invoice_firm_invoice_number', 'invoices', type_='unique')
