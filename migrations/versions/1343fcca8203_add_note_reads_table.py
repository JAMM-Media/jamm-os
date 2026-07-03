"""add note_reads table for per-user note read tracking

Revision ID: 1343fcca8203
Revises: 77c9106ec40b
Create Date: 2026-07-03 15:52:10.514993

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '1343fcca8203'
down_revision: Union[str, Sequence[str], None] = '77c9106ec40b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'note_reads',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('note_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['note_id'], ['notes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('note_id', 'user_id', name='uq_note_reads_note_user'),
    )
    op.create_index(op.f('ix_note_reads_note_id'), 'note_reads', ['note_id'], unique=False)
    op.create_index(op.f('ix_note_reads_user_id'), 'note_reads', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_note_reads_user_id'), table_name='note_reads')
    op.drop_index(op.f('ix_note_reads_note_id'), table_name='note_reads')
    op.drop_table('note_reads')
