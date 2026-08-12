# migrations/versions/e2f3g4h5i6j7_add_sequence_data_models.py

"""add sequence data models: Sequence, SequenceVersion, Step, StepEdge, SequenceGoal

Revision ID: e2f3g4h5i6j7
Revises: d2e3f4g5h6i7
Create Date: 2026-08-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e2f3g4h5i6j7'
down_revision: Union[str, Sequence, None] = 'd2e3f4g5h6i7'
branch_labels: Union[str, Sequence, None] = None
depends_on: Union[str, Sequence, None] = None


def upgrade() -> None:
    """Create five sequence tables. sequences.current_version_id is added as
    a deferred ALTER after sequence_versions exists, to resolve the circular FK."""

    # sequences -- current_version_id added after sequence_versions is created.
    op.create_table(
        'sequences',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sequences_firm_id', 'sequences', ['firm_id'])

    # sequence_versions
    op.create_table(
        'sequence_versions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('sequence_id', sa.Uuid(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('preset_lineage_key', sa.String(length=100), nullable=True),
        sa.Column('created_by_user_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['sequence_id'], ['sequences.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sequence_id', 'version_number', name='uq_sequence_version_number'),
    )
    op.create_index('ix_sequence_versions_sequence_id', 'sequence_versions', ['sequence_id'])
    op.create_index('ix_sequence_versions_preset_lineage_key', 'sequence_versions', ['preset_lineage_key'])

    # Add current_version_id to sequences now that sequence_versions exists.
    op.add_column(
        'sequences',
        sa.Column('current_version_id', sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        'fk_sequences_current_version_id',
        'sequences', 'sequence_versions',
        ['current_version_id'], ['id'],
        ondelete='SET NULL',
    )

    # sequence_steps
    op.create_table(
        'sequence_steps',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('sequence_version_id', sa.Uuid(), nullable=False),
        sa.Column('step_key', sa.String(length=50), nullable=False),
        sa.Column(
            'step_type',
            sa.Enum(
                'trigger', 'email', 'wait_fixed', 'wait_until_event',
                'branch', 'action', 'goal', 'won', 'dead_end',
                name='steptype', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('channel', sa.String(length=20), nullable=False, server_default='email'),
        sa.Column('phase', sa.String(length=50), nullable=True),
        sa.Column('is_modified_from_preset', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('config', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['sequence_version_id'], ['sequence_versions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sequence_version_id', 'step_key', name='uq_step_version_key'),
    )
    op.create_index('ix_sequence_steps_sequence_version_id', 'sequence_steps', ['sequence_version_id'])

    # sequence_step_edges
    op.create_table(
        'sequence_step_edges',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('from_step_id', sa.Uuid(), nullable=False),
        sa.Column('to_step_id', sa.Uuid(), nullable=False),
        sa.Column('condition_label', sa.String(length=50), nullable=True),
        sa.Column('loop_cap', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['from_step_id'], ['sequence_steps.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['to_step_id'], ['sequence_steps.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sequence_step_edges_from_step_id', 'sequence_step_edges', ['from_step_id'])
    op.create_index('ix_sequence_step_edges_to_step_id', 'sequence_step_edges', ['to_step_id'])

    # sequence_goals
    op.create_table(
        'sequence_goals',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('sequence_version_id', sa.Uuid(), nullable=False),
        sa.Column('goal_event', sa.String(length=100), nullable=False),
        sa.Column('target_step_id', sa.Uuid(), nullable=False),
        sa.Column('applies_to_phase', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['sequence_version_id'], ['sequence_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_step_id'], ['sequence_steps.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sequence_goals_sequence_version_id', 'sequence_goals', ['sequence_version_id'])


def downgrade() -> None:
    """Drop all five sequence tables in reverse dependency order."""
    op.drop_table('sequence_goals')
    op.drop_table('sequence_step_edges')
    op.drop_table('sequence_steps')
    # Drop current_version_id FK before dropping sequence_versions.
    op.drop_constraint('fk_sequences_current_version_id', 'sequences', type_='foreignkey')
    op.drop_column('sequences', 'current_version_id')
    op.drop_table('sequence_versions')
    op.drop_table('sequences')
