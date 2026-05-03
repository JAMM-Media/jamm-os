# migrations/versions/d1e2f3a4b5c6_phase9_notification_preferences.py

"""phase9_notification_preferences

Revision ID: d1e2f3a4b5c6
Revises: c9d8e7f6a5b4
Create Date: 2026-04-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd1e2f3a4b5c6'
down_revision = 'c9d8e7f6a5b4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'notification_preferences',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('firm_id', sa.UUID(), nullable=False),
        sa.Column('recipient_id', sa.UUID(), nullable=False),
        sa.Column('recipient_type', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('channel', sa.String(), nullable=False, server_default='both'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'firm_id', 'recipient_id', 'recipient_type', 'event_type',
            name='uq_notif_pref_recipient_event',
        ),
    )
    op.create_index(
        op.f('ix_notification_preferences_firm_id'),
        'notification_preferences',
        ['firm_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_notification_preferences_firm_id'),
        table_name='notification_preferences',
    )
    op.drop_table('notification_preferences')
