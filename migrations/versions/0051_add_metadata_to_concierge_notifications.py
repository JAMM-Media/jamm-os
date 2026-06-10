"""add metadata to concierge_notifications

Revision ID: 0051_add_metadata_to_concierge_notifications
Revises: 0ab2e3586a9c
Create Date: 2026-06-10

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0051_add_metadata_to_concierge_notifications'
down_revision: Union[str, Sequence[str], None] = '0ab2e3586a9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('concierge_notifications', sa.Column('metadata', sa.JSON(), nullable=True))
    # Rename index to match current model __table_args__
    op.drop_index('ix_concierge_notifications_firm_id_is_read', table_name='concierge_notifications', if_exists=True)
    op.create_index('ix_concierge_notification_firm_is_read', 'concierge_notifications', ['firm_id', 'is_read'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_concierge_notification_firm_is_read', table_name='concierge_notifications')
    op.create_index('ix_concierge_notifications_firm_id_is_read', 'concierge_notifications', ['firm_id', 'is_read'], unique=False)
    op.drop_column('concierge_notifications', 'metadata')
