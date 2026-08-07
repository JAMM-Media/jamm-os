"""add cooperative aliases

Revision ID: x1y2z3a4b5c6
Revises: w1x2y3z4a5b6
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'x1y2z3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'w1x2y3z4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'cooperative_aliases',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('owner_member_id', sa.Uuid(), nullable=False),
        sa.Column('target_member_id', sa.Uuid(), nullable=False),
        sa.Column('label', sa.String(128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['owner_member_id'], ['cooperative_members.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_member_id'], ['cooperative_members.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('owner_member_id', 'target_member_id', name='uq_cooperative_alias_owner_target'),
    )
    op.create_index(op.f('ix_cooperative_aliases_owner_member_id'), 'cooperative_aliases', ['owner_member_id'], unique=False)
    op.create_index(op.f('ix_cooperative_aliases_target_member_id'), 'cooperative_aliases', ['target_member_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_cooperative_aliases_target_member_id'), table_name='cooperative_aliases')
    op.drop_index(op.f('ix_cooperative_aliases_owner_member_id'), table_name='cooperative_aliases')
    op.drop_table('cooperative_aliases')
