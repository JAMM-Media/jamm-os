"""add mentions column to peer_network_messages

Revision ID: q1r2s3t4u5v6
Revises: p1q2r3s4t5u6
Create Date: 2026-08-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'q1r2s3t4u5v6'
down_revision: Union[str, Sequence[str], None] = 'p1q2r3s4t5u6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add mentions (JSON list of member UUIDs) to peer_network_messages."""
    op.add_column(
        'peer_network_messages',
        sa.Column('mentions', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Remove mentions from peer_network_messages."""
    op.drop_column('peer_network_messages', 'mentions')
