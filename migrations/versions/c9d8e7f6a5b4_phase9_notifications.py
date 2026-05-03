# migrations/versions/c9d8e7f6a5b4_phase9_notifications.py

"""phase9_notifications

Revision ID: c9d8e7f6a5b4
Revises: b1c2d3e4f5a6
Create Date: 2026-04-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c9d8e7f6a5b4'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'notifications',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('firm_id', sa.UUID(), nullable=False),
        sa.Column('recipient_id', sa.UUID(), nullable=False),
        sa.Column('recipient_type', sa.String(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('notification_type', sa.String(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('related_entity_type', sa.String(100), nullable=True),
        sa.Column('related_entity_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_notifications_firm_id'), 'notifications', ['firm_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_notifications_firm_id'), table_name='notifications')
    op.drop_table('notifications')
