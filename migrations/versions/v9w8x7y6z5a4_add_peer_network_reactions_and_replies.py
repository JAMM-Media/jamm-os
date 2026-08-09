"""add peer_network_reactions and parent_id to messages

Revision ID: v9w8x7y6z5a4
Revises: t1u2v3w4x5y6
Create Date: 2026-08-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'v9w8x7y6z5a4'
down_revision: Union[str, Sequence[str], None] = 't1u2v3w4x5y6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add parent_id to peer_network_messages; create peer_network_reactions."""
    op.add_column(
        'peer_network_messages',
        sa.Column('parent_id', sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        'fk_peer_network_messages_parent_id',
        'peer_network_messages',
        'peer_network_messages',
        ['parent_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_peer_network_messages_parent_id', 'peer_network_messages', ['parent_id'])

    op.create_table(
        'peer_network_reactions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('message_id', sa.Uuid(), nullable=False),
        sa.Column('member_id', sa.Uuid(), nullable=False),
        sa.Column('emoji', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], ['peer_network_messages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['member_id'], ['peer_network_members.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('message_id', 'member_id', 'emoji', name='uq_peer_network_reaction'),
    )
    op.create_index('ix_peer_network_reactions_message_id', 'peer_network_reactions', ['message_id'])
    op.create_index('ix_peer_network_reactions_member_id', 'peer_network_reactions', ['member_id'])


def downgrade() -> None:
    """Remove peer_network_reactions; remove parent_id from messages."""
    op.drop_index('ix_peer_network_reactions_member_id', table_name='peer_network_reactions')
    op.drop_index('ix_peer_network_reactions_message_id', table_name='peer_network_reactions')
    op.drop_table('peer_network_reactions')
    op.drop_index('ix_peer_network_messages_parent_id', table_name='peer_network_messages')
    op.drop_constraint('fk_peer_network_messages_parent_id', 'peer_network_messages', type_='foreignkey')
    op.drop_column('peer_network_messages', 'parent_id')
