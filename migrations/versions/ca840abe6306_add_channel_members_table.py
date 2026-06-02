"""add channel members table

Revision ID: ca840abe6306
Revises: b58c35fa26bc
Create Date: 2026-05-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ca840abe6306'
down_revision: Union[str, Sequence[str], None] = 'b58c35fa26bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('channel_members',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('channel_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('channel_id', 'user_id', name='uq_channel_member')
    )
    op.create_index(op.f('ix_channel_members_channel_id'), 'channel_members', ['channel_id'], unique=False)
    op.create_index(op.f('ix_channel_members_user_id'), 'channel_members', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_channel_members_user_id'), table_name='channel_members')
    op.drop_index(op.f('ix_channel_members_channel_id'), table_name='channel_members')
    op.drop_table('channel_members')
