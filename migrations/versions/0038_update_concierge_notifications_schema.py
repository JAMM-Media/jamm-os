# migrations/versions/0038_update_concierge_notifications_schema.py

"""update_concierge_notifications_schema

Revision ID: 0038_update_concierge_notifications_schema
Revises: 0037_add_concierge_question_log_and_notifications
Create Date: 2026-05-30

Replace sent_at/dismissed_at with created_at/is_read to match Phase 3
trigger layer requirements.
"""

from alembic import op
import sqlalchemy as sa

revision = '0038_update_concierge_notifications_schema'
down_revision = '0037_add_concierge_question_log_and_notifications'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'concierge_notifications',
        'sent_at',
        new_column_name='created_at',
    )

    op.drop_column('concierge_notifications', 'dismissed_at')

    op.add_column(
        'concierge_notifications',
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
    )

    op.drop_index('ix_concierge_notification_firm_id', table_name='concierge_notifications')
    op.create_index(
        'ix_concierge_notification_firm_is_read',
        'concierge_notifications',
        ['firm_id', 'is_read'],
    )


def downgrade():
    op.drop_index('ix_concierge_notification_firm_is_read', table_name='concierge_notifications')
    op.create_index('ix_concierge_notification_firm_id', 'concierge_notifications', ['firm_id'])

    op.drop_column('concierge_notifications', 'is_read')

    op.add_column(
        'concierge_notifications',
        sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.alter_column(
        'concierge_notifications',
        'created_at',
        new_column_name='sent_at',
    )
