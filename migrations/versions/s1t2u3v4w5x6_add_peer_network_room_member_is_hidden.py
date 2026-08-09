"""add is_hidden to peer_network_room_members

Revision ID: s1t2u3v4w5x6
Revises: r1s2t3u4v5w6
Create Date: 2026-08-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 's1t2u3v4w5x6'
down_revision: Union[str, Sequence[str], None] = 'r1s2t3u4v5w6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_hidden to peer_network_room_members."""
    op.add_column(
        'peer_network_room_members',
        sa.Column('is_hidden', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    """Remove is_hidden from peer_network_room_members."""
    op.drop_column('peer_network_room_members', 'is_hidden')
