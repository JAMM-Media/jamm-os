"""add recurring engagements

Revision ID: 0035_recurring_engagements
Revises: 0034_add_qc_checklist_tables
Create Date: 2026-05-23

"""
from alembic import op
import sqlalchemy as sa

revision = '0035_recurring_engagements'
down_revision = '0034_add_qc_checklist_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Add recurring columns to engagement_templates
    op.add_column('engagement_templates', sa.Column('is_recurring', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('engagement_templates', sa.Column('recurrence_cadence', sa.String(20), nullable=True))
    op.add_column('engagement_templates', sa.Column('recurrence_day', sa.Integer(), nullable=True))
    op.add_column('engagement_templates', sa.Column('recurrence_month', sa.Integer(), nullable=True))
    op.add_column('engagement_templates', sa.Column('recurrence_advance_days', sa.Integer(), nullable=True, server_default='14'))
    op.add_column('engagement_templates', sa.Column('last_spawned_at', sa.DateTime(timezone=True), nullable=True))

    op.create_index(
        'ix_engagement_templates_is_recurring',
        'engagement_templates', ['is_recurring']
    )

    # Create recurring_engagement_log table
    op.create_table(
        'recurring_engagement_log',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('firm_id', sa.UUID(), nullable=False),
        sa.Column('template_id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=False),
        sa.Column('engagement_id', sa.UUID(), nullable=False),
        sa.Column('spawned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['template_id'], ['engagement_templates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_recurring_engagement_log_template_id', 'recurring_engagement_log', ['template_id'])
    op.create_index('ix_recurring_engagement_log_firm_id', 'recurring_engagement_log', ['firm_id'])


def downgrade():
    op.drop_index('ix_recurring_engagement_log_firm_id', table_name='recurring_engagement_log')
    op.drop_index('ix_recurring_engagement_log_template_id', table_name='recurring_engagement_log')
    op.drop_table('recurring_engagement_log')

    op.drop_index('ix_engagement_templates_is_recurring', table_name='engagement_templates')
    op.drop_column('engagement_templates', 'last_spawned_at')
    op.drop_column('engagement_templates', 'recurrence_advance_days')
    op.drop_column('engagement_templates', 'recurrence_month')
    op.drop_column('engagement_templates', 'recurrence_day')
    op.drop_column('engagement_templates', 'recurrence_cadence')
    op.drop_column('engagement_templates', 'is_recurring')
