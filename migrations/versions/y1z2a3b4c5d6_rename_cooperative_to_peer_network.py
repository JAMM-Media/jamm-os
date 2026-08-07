"""rename cooperative to peer network

Revision ID: y1z2a3b4c5d6
Revises: x1y2z3a4b5c6
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'y1z2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'x1y2z3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename cooperative tables and Firm column. Safe, non-destructive -- preserves all data."""
    op.rename_table('cooperative_members', 'peer_network_members')
    op.rename_table('cooperative_rooms', 'peer_network_rooms')
    op.rename_table('cooperative_messages', 'peer_network_messages')
    op.rename_table('cooperative_aliases', 'peer_network_aliases')
    op.alter_column('firms', 'cooperative_enabled', new_column_name='peer_network_enabled')


def downgrade() -> None:
    """Reverse the rename."""
    op.alter_column('firms', 'peer_network_enabled', new_column_name='cooperative_enabled')
    op.rename_table('peer_network_aliases', 'cooperative_aliases')
    op.rename_table('peer_network_messages', 'cooperative_messages')
    op.rename_table('peer_network_rooms', 'cooperative_rooms')
    op.rename_table('peer_network_members', 'cooperative_members')
