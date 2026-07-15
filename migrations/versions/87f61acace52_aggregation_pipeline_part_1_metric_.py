"""aggregation pipeline part 1 metric value run log preset lineage

Revision ID: 87f61acace52
Revises: e0cff1ee10ea
Create Date: 2026-07-14 18:43:56.167571

Covers Step 2A item 3 (AutomationRule preset lineage columns), Step 2C
(MetricValue, MetricRunLog, metric_registry.window_type), and Step 2D
(deactivate the portal_utilization_todos registry row).

preset_key backfill: NOT performed. There is no persisted field today
linking an existing automation_rules row back to the preset it was seeded
from -- seed_firm_presets() constructs rows directly from
_get_preset_rules() dicts with no lineage marker, and any origin inferred
from (trigger_event, name, actions) would be a content-similarity guess,
not a determination, and would silently misclassify any already-customized
preset-derived rule (whose actions no longer match the preset template) as
a pure custom rule with no way to correct it later, since preset_key is
never cleared once set. Per the task's own instruction, this is reported
rather than guessed. All existing rows get preset_key = NULL; only rules
seeded from this point forward carry lineage.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '87f61acace52'
down_revision: Union[str, Sequence[str], None] = 'e0cff1ee10ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('metric_run_logs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.Enum('running', 'succeeded', 'failed', name='metricrunstatus', native_enum=False), nullable=False),
    sa.Column('error_summary', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('metric_values',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('firm_id', sa.Uuid(), nullable=False),
    sa.Column('metric_id', sa.UUID(), nullable=False),
    sa.Column('week_start', sa.Date(), nullable=False),
    sa.Column('value', sa.Numeric(precision=12, scale=4), nullable=True),
    sa.Column('sample_size', sa.Integer(), nullable=False),
    sa.Column('std_dev', sa.Numeric(precision=12, scale=4), nullable=True),
    sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['metric_id'], ['metric_registry.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('firm_id', 'metric_id', 'week_start', name='uq_metric_value_firm_metric_week')
    )
    op.create_index(op.f('ix_metric_values_firm_id'), 'metric_values', ['firm_id'], unique=False)
    op.create_index(op.f('ix_metric_values_metric_id'), 'metric_values', ['metric_id'], unique=False)

    # preset_key intentionally left nullable with no backfill -- see revision
    # docstring. is_customized defaults false for every existing row, which
    # is accurate: nothing had a way to be "customized" before this column existed.
    op.add_column('automation_rules', sa.Column('preset_key', sa.String(), nullable=True))
    op.add_column('automation_rules', sa.Column('is_customized', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.create_index(op.f('ix_automation_rules_preset_key'), 'automation_rules', ['preset_key'], unique=False)

    # window_type: add nullable, backfill per row, then enforce not null.
    op.add_column('metric_registry', sa.Column('window_type', sa.Enum('weekly_summary', 'rolling_snapshot', name='metricwindowtype', native_enum=False), nullable=True))
    op.execute("UPDATE metric_registry SET window_type = 'rolling_snapshot' WHERE key = 'automation_utilization'")
    op.execute("UPDATE metric_registry SET window_type = 'weekly_summary' WHERE key != 'automation_utilization'")
    op.alter_column('metric_registry', 'window_type', nullable=False)

    # Step 2D -- portal_utilization_todos deactivated (row kept, not deleted).
    op.execute("UPDATE metric_registry SET is_active = false WHERE key = 'portal_utilization_todos'")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE metric_registry SET is_active = true WHERE key = 'portal_utilization_todos'")
    op.drop_column('metric_registry', 'window_type')
    op.drop_index(op.f('ix_automation_rules_preset_key'), table_name='automation_rules')
    op.drop_column('automation_rules', 'is_customized')
    op.drop_column('automation_rules', 'preset_key')
    op.drop_index(op.f('ix_metric_values_metric_id'), table_name='metric_values')
    op.drop_index(op.f('ix_metric_values_firm_id'), table_name='metric_values')
    op.drop_table('metric_values')
    op.drop_table('metric_run_logs')
