# migrations/versions/ce1f48a31ce8_add_surface_items_and_engagements_completed_at.py

"""add surface_items and engagements.completed_at

Hand-written. Autogenerate was run first, per the migration procedure, and its
output carried the two intended changes plus roughly twenty-three unrelated
drift items already known to stand between the models and the dev database:
dashboard_layouts and firm_default_dashboard_layouts unique-constraint
reshuffles, the peer_network cooperative-era index renames, a leads.entity_type
column comment, and, most importantly, a DROP of the partial unique index
uq_enrollment_active_lead_sequence, which is real enforced behavior with a
guard test of its own. None of that belongs to this build, and the drop would
have been destructive, so the generated file was deleted and this one written
by hand containing only what this session added.

Revision ID: ce1f48a31ce8
Revises: 611faa198fe7
Create Date: 2026-09-01 18:43:38.603156

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ce1f48a31ce8'
down_revision: Union[str, Sequence[str], None] = '611faa198fe7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'surface_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column(
            'kind',
            sa.Enum('briefing', 'observatory', name='surfacekind', native_enum=False),
            nullable=False,
        ),
        sa.Column('finding_id', sa.UUID(), nullable=True),
        sa.Column('item_type', sa.String(length=100), nullable=False),
        sa.Column('dedup_key', sa.String(length=255), nullable=False),
        sa.Column('headline', sa.String(length=500), nullable=False),
        sa.Column(
            'payload',
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column('rank', sa.Integer(), server_default='0', nullable=False),
        sa.Column('slotted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('appearance_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('last_served_on', sa.Date(), nullable=True),
        sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'dismissal_reason',
            sa.Enum(
                'not_relevant', 'already_handling', 'was_wrong',
                name='dismissalreason', native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column('implemented_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('suppressed_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'value_at_action',
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column('flagged_for_review', sa.Boolean(), server_default='false', nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['finding_id'], ['findings.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_surface_items_finding', 'surface_items', ['finding_id'], unique=False)
    op.create_index(
        op.f('ix_surface_items_firm_id'), 'surface_items', ['firm_id'], unique=False
    )
    op.create_index(
        'ix_surface_items_firm_kind', 'surface_items', ['firm_id', 'kind'], unique=False
    )
    op.create_index(
        'ix_surface_items_firm_kind_rank',
        'surface_items',
        ['firm_id', 'kind', 'rank'],
        unique=False,
        postgresql_where=sa.text('resolved_at IS NULL'),
    )
    # One live row per condition instance per surface. Declared on the model
    # as well, because conftest builds the test database with create_all() and
    # a migration-only index would be absent from every test run.
    op.create_index(
        'uq_surface_items_open_condition',
        'surface_items',
        ['firm_id', 'kind', 'item_type', 'dedup_key'],
        unique=True,
        postgresql_where=sa.text('resolved_at IS NULL'),
    )

    # Nullable with no backfill, by ruling: engagements completed before this
    # column existed stay NULL, and work_unbilled only fires for completions
    # recorded after it landed.
    op.add_column(
        'engagements',
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('engagements', 'completed_at')

    op.drop_index('uq_surface_items_open_condition', table_name='surface_items')
    op.drop_index('ix_surface_items_firm_kind_rank', table_name='surface_items')
    op.drop_index('ix_surface_items_firm_kind', table_name='surface_items')
    op.drop_index(op.f('ix_surface_items_firm_id'), table_name='surface_items')
    op.drop_index('ix_surface_items_finding', table_name='surface_items')
    op.drop_table('surface_items')
