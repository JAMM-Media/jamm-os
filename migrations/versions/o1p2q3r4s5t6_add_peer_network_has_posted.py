"""add peer_network_members.has_posted

Revision ID: o1p2q3r4s5t6
Revises: n1o2p3q4r5s6
Create Date: 2026-08-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'o1p2q3r4s5t6'
down_revision: Union[str, Sequence[str], None] = 'n1o2p3q4r5s6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add has_posted to peer_network_members."""
    op.add_column(
        'peer_network_members',
        sa.Column('has_posted', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    """Remove has_posted from peer_network_members."""
    op.drop_column('peer_network_members', 'has_posted')
