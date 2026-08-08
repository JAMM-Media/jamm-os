"""add message edit and delete to peer_network_messages

Revision ID: z1a2b3c4d5e6
Revises: y1z2a3b4c5d6
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'z1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'y1z2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add edited_at and is_deleted to peer_network_messages."""
    op.add_column(
        'peer_network_messages',
        sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'peer_network_messages',
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    """Remove edited_at and is_deleted from peer_network_messages."""
    op.drop_column('peer_network_messages', 'is_deleted')
    op.drop_column('peer_network_messages', 'edited_at')
