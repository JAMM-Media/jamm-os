"""add dashboard_layouts and firm_default_dashboard_layouts

Revision ID: m1n2o3p4q5r6
Revises: edf14bcf2539
Create Date: 2026-08-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'm1n2o3p4q5r6'
down_revision: Union[str, Sequence[str], None] = 'edf14bcf2539'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'dashboard_layouts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('widgets', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_dashboard_layouts_user_id'),
    )
    op.create_index(op.f('ix_dashboard_layouts_firm_id'), 'dashboard_layouts', ['firm_id'], unique=False)
    op.create_index(op.f('ix_dashboard_layouts_user_id'), 'dashboard_layouts', ['user_id'], unique=False)

    op.create_table(
        'firm_default_dashboard_layouts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('widgets', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('firm_id', name='uq_firm_default_dashboard_layouts_firm_id'),
    )
    op.create_index(op.f('ix_firm_default_dashboard_layouts_firm_id'), 'firm_default_dashboard_layouts', ['firm_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_firm_default_dashboard_layouts_firm_id'), table_name='firm_default_dashboard_layouts')
    op.drop_table('firm_default_dashboard_layouts')
    op.drop_index(op.f('ix_dashboard_layouts_user_id'), table_name='dashboard_layouts')
    op.drop_index(op.f('ix_dashboard_layouts_firm_id'), table_name='dashboard_layouts')
    op.drop_table('dashboard_layouts')
