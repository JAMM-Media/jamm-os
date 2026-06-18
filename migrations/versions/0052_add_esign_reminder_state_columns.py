# migrations/versions/0052_add_esign_reminder_state_columns.py

"""add_esign_reminder_state_columns

Revision ID: 0052_add_esign_reminder_state_columns
Revises: 0051_add_metadata_to_concierge_notifications
Create Date: 2026-06-18

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision = '0052_add_esign_reminder_state_columns'
down_revision = '0051_add_metadata_to_concierge_notifications'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('signature_envelopes', sa.Column('auto_reminder_sent_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('signature_envelopes', sa.Column('escalated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('signature_envelopes', sa.Column('followup_task_id', sa.UUID(), nullable=True))


def downgrade():
    op.drop_column('signature_envelopes', 'followup_task_id')
    op.drop_column('signature_envelopes', 'escalated_at')
    op.drop_column('signature_envelopes', 'auto_reminder_sent_at')
