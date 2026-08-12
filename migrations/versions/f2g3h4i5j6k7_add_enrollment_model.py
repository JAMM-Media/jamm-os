# migrations/versions/f2g3h4i5j6k7_add_enrollment_model.py

"""add enrollment model with partial unique index

Revision ID: f2g3h4i5j6k7
Revises: e2f3g4h5i6j7
Create Date: 2026-08-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f2g3h4i5j6k7'
down_revision: Union[str, Sequence, None] = 'e2f3g4h5i6j7'
branch_labels: Union[str, Sequence, None] = None
depends_on: Union[str, Sequence, None] = None


def upgrade() -> None:
    """Create enrollments table with partial unique index enforcing no-duplicate-concurrent-enrollment.

    The partial unique index is on (lead_id, sequence_id) WHERE status = 'active'.
    Keyed on the SEQUENCE (not version) so a lead cannot be enrolled twice in the same
    nurture preset even across two different versions of it.
    """
    op.create_table(
        'enrollments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('lead_id', sa.Uuid(), nullable=False),
        sa.Column('sequence_id', sa.Uuid(), nullable=False),
        sa.Column('sequence_version_id', sa.Uuid(), nullable=False),
        sa.Column('current_step_id', sa.Uuid(), nullable=True),
        sa.Column('next_action_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'status',
            sa.Enum(
                'active', 'unsubscribed', 'converted',
                'removed_by_staff', 'completed_dead_end', 'completed_won',
                name='enrollmentstatus', native_enum=False,
            ),
            nullable=False,
            server_default='active',
        ),
        sa.Column('loop_counts', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('enrolled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('stopped_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sequence_id'], ['sequences.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sequence_version_id'], ['sequence_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['current_step_id'], ['sequence_steps.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index('ix_enrollments_firm_id', 'enrollments', ['firm_id'])
    op.create_index('ix_enrollments_lead_id', 'enrollments', ['lead_id'])
    op.create_index('ix_enrollments_sequence_id', 'enrollments', ['sequence_id'])
    op.create_index('ix_enrollments_sequence_version_id', 'enrollments', ['sequence_version_id'])

    # Partial unique index: no two active enrollments for the same lead in the same sequence.
    op.create_index(
        'uq_enrollment_active_lead_sequence',
        'enrollments',
        ['lead_id', 'sequence_id'],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    """Drop enrollments table and all associated indexes."""
    op.drop_index('uq_enrollment_active_lead_sequence', table_name='enrollments')
    op.drop_index('ix_enrollments_sequence_version_id', table_name='enrollments')
    op.drop_index('ix_enrollments_sequence_id', table_name='enrollments')
    op.drop_index('ix_enrollments_lead_id', table_name='enrollments')
    op.drop_index('ix_enrollments_firm_id', table_name='enrollments')
    op.drop_table('enrollments')
