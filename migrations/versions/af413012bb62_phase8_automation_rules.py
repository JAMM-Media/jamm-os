"""phase8_automation_rules

Revision ID: af413012bb62
Revises: 2a0842dc2d3c
Create Date: 2026-03-31 11:50:19.937944

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'af413012bb62'
down_revision: Union[str, Sequence[str], None] = '2a0842dc2d3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'automation_rules',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column(
            'trigger_event',
            sa.Enum(
                'engagement_created', 'engagement_status_changed', 'engagement_completed',
                'engagement_overdue', 'engagement_recurrence_created',
                'doc_request_created', 'doc_request_item_uploaded', 'doc_request_completed',
                'doc_request_reminder_sent',
                'esign_sent', 'esign_signed', 'esign_declined', 'esign_expired',
                'esign_reminder_sent',
                'invoice_created', 'invoice_sent', 'invoice_paid', 'invoice_overdue',
                'time_entry_created', 'task_assigned', 'task_reassigned',
                'client_created', 'intake_form_submitted',
                name='triggerevent',
            ),
            nullable=False,
        ),
        sa.Column('trigger_conditions', sa.JSON(), nullable=False),
        sa.Column('actions', sa.JSON(), nullable=False),
        sa.Column('execution_count', sa.Integer(), nullable=False),
        sa.Column('last_executed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_automation_rules_firm_id'), 'automation_rules', ['firm_id'], unique=False)
    op.create_index(op.f('ix_automation_rules_trigger_event'), 'automation_rules', ['trigger_event'], unique=False)

    op.create_table(
        'automation_execution_logs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('rule_id', sa.Uuid(), nullable=False),
        sa.Column(
            'trigger_event',
            sa.Enum(
                'engagement_created', 'engagement_status_changed', 'engagement_completed',
                'engagement_overdue', 'engagement_recurrence_created',
                'doc_request_created', 'doc_request_item_uploaded', 'doc_request_completed',
                'doc_request_reminder_sent',
                'esign_sent', 'esign_signed', 'esign_declined', 'esign_expired',
                'esign_reminder_sent',
                'invoice_created', 'invoice_sent', 'invoice_paid', 'invoice_overdue',
                'time_entry_created', 'task_assigned', 'task_reassigned',
                'client_created', 'intake_form_submitted',
                name='triggerevent',
            ),
            nullable=False,
        ),
        sa.Column('trigger_payload', sa.JSON(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('success', 'failed', 'partial', 'skipped', name='automationexecutionstatus'),
            nullable=False,
        ),
        sa.Column('actions_executed', sa.JSON(), nullable=False),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id']),
        sa.ForeignKeyConstraint(['rule_id'], ['automation_rules.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_automation_execution_logs_firm_id'), 'automation_execution_logs', ['firm_id'], unique=False)
    op.create_index(op.f('ix_automation_execution_logs_rule_id'), 'automation_execution_logs', ['rule_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_automation_execution_logs_rule_id'), table_name='automation_execution_logs')
    op.drop_index(op.f('ix_automation_execution_logs_firm_id'), table_name='automation_execution_logs')
    op.drop_table('automation_execution_logs')
    op.drop_index(op.f('ix_automation_rules_trigger_event'), table_name='automation_rules')
    op.drop_index(op.f('ix_automation_rules_firm_id'), table_name='automation_rules')
    op.drop_table('automation_rules')
    op.execute('DROP TYPE IF EXISTS triggerevent')
    op.execute('DROP TYPE IF EXISTS automationexecutionstatus')
