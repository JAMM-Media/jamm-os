# migrations/versions/0037_add_concierge_question_log_and_notifications.py

"""add_concierge_question_log_and_notifications

Revision ID: 0037_add_concierge_question_log_and_notifications
Revises: 0036_add_concierge_fields_to_firm
Create Date: 2026-05-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0037_add_concierge_question_log_and_notifications'
down_revision = '0036_add_concierge_fields_to_firm'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'concierge_question_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('firm_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('response_summary', sa.Text(), nullable=True),
        sa.Column('low_confidence', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('asked_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('reviewed', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_concierge_question_log_firm_id', 'concierge_question_logs', ['firm_id'])
    op.create_index('ix_concierge_question_log_low_confidence', 'concierge_question_logs', ['low_confidence'])

    op.create_table(
        'concierge_notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('firm_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('trigger_type', sa.String(60), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_concierge_notification_firm_id', 'concierge_notifications', ['firm_id'])


def downgrade():
    op.drop_index('ix_concierge_notification_firm_id', table_name='concierge_notifications')
    op.drop_table('concierge_notifications')

    op.drop_index('ix_concierge_question_log_low_confidence', table_name='concierge_question_logs')
    op.drop_index('ix_concierge_question_log_firm_id', table_name='concierge_question_logs')
    op.drop_table('concierge_question_logs')
