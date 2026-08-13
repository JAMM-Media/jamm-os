# migrations/versions/d2e3f4g5h6i7_add_converted_client_id_to_leads.py

"""add converted_client_id to leads

Revision ID: d2e3f4g5h6i7
Revises: c2d3e4f5g6h7
Create Date: 2026-08-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd2e3f4g5h6i7'
down_revision: Union[str, Sequence[str], None] = 'c2d3e4f5g6h7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add converted_client_id FK to leads -- set when a lead wins and becomes a Client."""
    op.add_column(
        'leads',
        sa.Column('converted_client_id', sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        'fk_leads_converted_client_id_clients',
        'leads', 'clients',
        ['converted_client_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Remove converted_client_id from leads."""
    op.drop_constraint('fk_leads_converted_client_id_clients', 'leads', type_='foreignkey')
    op.drop_column('leads', 'converted_client_id')
