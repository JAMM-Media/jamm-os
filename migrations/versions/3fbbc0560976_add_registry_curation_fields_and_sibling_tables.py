"""add registry curation fields and sibling tables

Revision ID: 3fbbc0560976
Revises: 4d538ddb5404
Create Date: 2026-09-10 08:58:30.356777

Hand-written per Section 2 of the Sep 10, 2026 task file. Autogenerate
proposed this content plus the standing drift inventory (dashboard layout
indexes, the enrollment partial index, the peer_network index renames, the
notifications.tier type, two column comments, and a document_folders index),
none of which belongs to this session, so that file was deleted and this one
carries only the registry curation change.

Nothing here is native: every sa.Enum is native_enum=False, so no CREATE TYPE
is emitted and downgrade has no DROP TYPE to run.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3fbbc0560976'
down_revision: Union[str, Sequence[str], None] = '4d538ddb5404'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Display curation fields on metric_registry. All ship NULL or empty;
    # the authoring session fills them (ruling R6).
    op.add_column(
        'metric_registry',
        sa.Column(
            'pillar',
            sa.Enum(
                'client_intake', 'performance', 'retention_and_growth',
                name='metricpillar', native_enum=False,
            ),
            nullable=True,
        ),
    )
    op.add_column(
        'metric_registry',
        sa.Column(
            'entity_type',
            sa.Enum(
                'lead', 'client', 'engagement', 'task', 'document',
                'document_request', 'invoice', 'envelope',
                'automation_preset', 'firm',
                name='metricentitytype', native_enum=False,
            ),
            nullable=True,
        ),
    )
    op.add_column(
        'metric_registry',
        sa.Column('attention_weight', sa.Integer(), nullable=True),
    )
    op.add_column(
        'metric_registry',
        sa.Column(
            'synonyms',
            postgresql.ARRAY(sa.String(length=100)),
            server_default='{}',
            nullable=False,
        ),
    )

    # Directional related metrics (rulings R4).
    op.create_table(
        'metric_registry_relations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('metric_id', sa.UUID(), nullable=False),
        sa.Column('related_metric_id', sa.UUID(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('metric_id != related_metric_id', name='ck_metric_registry_relations_not_self'),
        sa.ForeignKeyConstraint(['metric_id'], ['metric_registry.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['related_metric_id'], ['metric_registry.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('metric_id', 'related_metric_id', name='uq_metric_registry_relations_pair'),
    )
    op.create_index(op.f('ix_metric_registry_relations_metric_id'), 'metric_registry_relations', ['metric_id'], unique=False)
    op.create_index(op.f('ix_metric_registry_relations_related_metric_id'), 'metric_registry_relations', ['related_metric_id'], unique=False)

    # Sliceable axes, one list per metric (rulings R1, R2, R3, R5).
    op.create_table(
        'metric_registry_axes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('metric_id', sa.UUID(), nullable=False),
        sa.Column(
            'axis_kind',
            sa.Enum(
                'engagement_category', 'complexity_flag',
                'complexity_dimension', 'referral_source',
                name='metricaxiskind', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('axis_key', sa.String(length=200), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['metric_id'], ['metric_registry.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('metric_id', 'axis_kind', 'axis_key', name='uq_metric_registry_axes_metric_kind_key'),
    )
    op.create_index(op.f('ix_metric_registry_axes_metric_id'), 'metric_registry_axes', ['metric_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema. Reverse order of upgrade; nothing native to drop."""
    op.drop_index(op.f('ix_metric_registry_axes_metric_id'), table_name='metric_registry_axes')
    op.drop_table('metric_registry_axes')

    op.drop_index(op.f('ix_metric_registry_relations_related_metric_id'), table_name='metric_registry_relations')
    op.drop_index(op.f('ix_metric_registry_relations_metric_id'), table_name='metric_registry_relations')
    op.drop_table('metric_registry_relations')

    op.drop_column('metric_registry', 'synonyms')
    op.drop_column('metric_registry', 'attention_weight')
    op.drop_column('metric_registry', 'entity_type')
    op.drop_column('metric_registry', 'pillar')
