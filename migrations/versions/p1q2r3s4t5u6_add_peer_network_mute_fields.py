"""add mute fields to peer_network_members

Revision ID: p1q2r3s4t5u6
Revises: o1p2q3r4s5t6
Create Date: 2026-08-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'p1q2r3s4t5u6'
down_revision: Union[str, Sequence[str], None] = 'o1p2q3r4s5t6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_muted, muted_reason, muted_at, muted_by to peer_network_members."""
    op.add_column(
        'peer_network_members',
        sa.Column('is_muted', sa.Boolean(), nullable=False, server_default='false'),
    )
    op.add_column(
        'peer_network_members',
        sa.Column('muted_reason', sa.String(512), nullable=True),
    )
    op.add_column(
        'peer_network_members',
        sa.Column('muted_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'peer_network_members',
        sa.Column('muted_by', sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        'fk_peer_network_members_muted_by_users',
        'peer_network_members',
        'users',
        ['muted_by'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Remove mute fields from peer_network_members."""
    op.drop_constraint(
        'fk_peer_network_members_muted_by_users',
        'peer_network_members',
        type_='foreignkey',
    )
    op.drop_column('peer_network_members', 'muted_by')
    op.drop_column('peer_network_members', 'muted_at')
    op.drop_column('peer_network_members', 'muted_reason')
    op.drop_column('peer_network_members', 'is_muted')
