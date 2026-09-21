"""add created_at to stripe_connections

Revision ID: 4e1768d22b34
Revises: 22aa77d2697a
Create Date: 2026-09-21 12:02:33.844906

Every model in this codebase requires created_at and updated_at,
timezone-aware. stripe_connections had updated_at and connected_at
but no created_at. connected_at is not a substitute: a connection
can disconnect and reconnect, overwriting connected_at, while
created_at should be the one true record of row creation and never
change after insert.

Existing rows are backfilled from connected_at, the closest real
approximation available for rows that predate this column.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e1768d22b34'
down_revision: Union[str, Sequence[str], None] = '22aa77d2697a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add as nullable first so the backfill UPDATE can run before we enforce NOT NULL.
    op.add_column(
        'stripe_connections',
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    )
    # Backfill existing rows from connected_at -- the closest real approximation
    # of row creation for any row that predates this column.
    op.execute('UPDATE stripe_connections SET created_at = connected_at')
    # All rows now have a value; safe to enforce NOT NULL and add the server default.
    op.alter_column(
        'stripe_connections',
        'created_at',
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text('now()'),
    )


def downgrade() -> None:
    op.drop_column('stripe_connections', 'created_at')
