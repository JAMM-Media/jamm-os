"""add growth cooperative

Revision ID: w1x2y3z4a5b6
Revises: v1w2x3y4z5a6
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'w1x2y3z4a5b6'
down_revision: Union[str, Sequence[str], None] = 'v1w2x3y4z5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add firm-level opt-in flag to firms table.
    op.add_column(
        'firms',
        sa.Column('cooperative_enabled', sa.Boolean(), nullable=False, server_default='false'),
    )

    # CooperativeRoom -- created before members and messages since both FK to it.
    op.create_table(
        'cooperative_rooms',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('room_type', sa.String(32), nullable=False),
        sa.Column('name', sa.String(128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # CooperativeMember.
    op.create_table(
        'cooperative_members',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('handle', sa.String(64), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_jamm_team', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('granted_by', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['granted_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_cooperative_members_user_id'),
        sa.UniqueConstraint('handle', name='uq_cooperative_members_handle'),
    )
    op.create_index(op.f('ix_cooperative_members_user_id'), 'cooperative_members', ['user_id'], unique=False)
    op.create_index(op.f('ix_cooperative_members_firm_id'), 'cooperative_members', ['firm_id'], unique=False)

    # CooperativeMessage.
    op.create_table(
        'cooperative_messages',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('room_id', sa.Uuid(), nullable=False),
        sa.Column('author_member_id', sa.Uuid(), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['room_id'], ['cooperative_rooms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_member_id'], ['cooperative_members.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_cooperative_messages_room_id'), 'cooperative_messages', ['room_id'], unique=False)
    op.create_index(op.f('ix_cooperative_messages_author_member_id'), 'cooperative_messages', ['author_member_id'], unique=False)

    # Data migration: insert the singleton main room.
    op.execute(
        sa.text(
            "INSERT INTO cooperative_rooms (id, room_type, name, created_at) "
            "VALUES (:id, :room_type, :name, NOW())"
        ).bindparams(
            id=str(uuid.uuid4()),
            room_type='main',
            name=None,
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_cooperative_messages_author_member_id'), table_name='cooperative_messages')
    op.drop_index(op.f('ix_cooperative_messages_room_id'), table_name='cooperative_messages')
    op.drop_table('cooperative_messages')
    op.drop_index(op.f('ix_cooperative_members_firm_id'), table_name='cooperative_members')
    op.drop_index(op.f('ix_cooperative_members_user_id'), table_name='cooperative_members')
    op.drop_table('cooperative_members')
    op.drop_table('cooperative_rooms')
    op.drop_column('firms', 'cooperative_enabled')
