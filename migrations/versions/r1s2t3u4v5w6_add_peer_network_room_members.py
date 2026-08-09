"""add peer_network_room_members table

Revision ID: r1s2t3u4v5w6
Revises: q1r2s3t4u5v6
Create Date: 2026-08-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'r1s2t3u4v5w6'
down_revision: Union[str, Sequence[str], None] = 'q1r2s3t4u5v6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create peer_network_room_members table."""
    op.create_table(
        'peer_network_room_members',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('room_id', sa.Uuid(), nullable=False),
        sa.Column('member_id', sa.Uuid(), nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['room_id'], ['peer_network_rooms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['member_id'], ['peer_network_members.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('room_id', 'member_id', name='uq_peer_network_room_member'),
    )
    op.create_index('ix_peer_network_room_members_room_id', 'peer_network_room_members', ['room_id'])
    op.create_index('ix_peer_network_room_members_member_id', 'peer_network_room_members', ['member_id'])


def downgrade() -> None:
    """Drop peer_network_room_members table."""
    op.drop_index('ix_peer_network_room_members_member_id', table_name='peer_network_room_members')
    op.drop_index('ix_peer_network_room_members_room_id', table_name='peer_network_room_members')
    op.drop_table('peer_network_rooms_members')
