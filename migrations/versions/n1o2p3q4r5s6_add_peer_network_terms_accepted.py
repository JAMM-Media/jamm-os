"""add peer_network_members.terms_accepted_at

Revision ID: n1o2p3q4r5s6
Revises: z1a2b3c4d5e6
Create Date: 2026-08-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'n1o2p3q4r5s6'
down_revision: Union[str, Sequence[str], None] = 'z1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add terms_accepted_at to peer_network_members."""
    op.add_column(
        'peer_network_members',
        sa.Column('terms_accepted_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Remove terms_accepted_at from peer_network_members."""
    op.drop_column('peer_network_members', 'terms_accepted_at')
