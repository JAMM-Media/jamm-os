"""drop concierge_notifications table

Revision ID: 9703bc76ace7
Revises: a4d91c7b3e28
Create Date: 2026-09-26 15:27:06.219473

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9703bc76ace7'
down_revision: Union[str, Sequence[str], None] = 'a4d91c7b3e28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('ix_concierge_notification_firm_is_read', table_name='concierge_notifications')
    op.drop_index(
        'ux_concierge_notification_firm_trigger_unread',
        table_name='concierge_notifications',
        postgresql_where='(is_read = false)',
    )
    op.drop_table('concierge_notifications')


def downgrade() -> None:
    op.create_table(
        'concierge_notifications',
        sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
        sa.Column('firm_id', sa.UUID(), autoincrement=False, nullable=False),
        sa.Column('trigger_type', sa.VARCHAR(length=60), autoincrement=False, nullable=False),
        sa.Column('message', sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column('is_read', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False),
        sa.Column('dismissed_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], name='concierge_notifications_firm_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='concierge_notifications_pkey'),
    )
    op.create_index(
        'ux_concierge_notification_firm_trigger_unread',
        'concierge_notifications',
        ['firm_id', 'trigger_type'],
        unique=True,
        postgresql_where='(is_read = false)',
    )
    op.create_index(
        'ix_concierge_notification_firm_is_read',
        'concierge_notifications',
        ['firm_id', 'is_read'],
        unique=False,
    )
