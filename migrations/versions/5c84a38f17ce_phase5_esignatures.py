"""phase5_esignatures

Revision ID: 5c84a38f17ce
Revises: fec85debc26f
Create Date: 2026-03-24 18:44:30.202545

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c84a38f17ce'
down_revision: Union[str, Sequence[str], None] = 'fec85debc26f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — Phase 5: add engagement_letter_templates and signature_envelopes."""
    op.create_table('engagement_letter_templates',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('firm_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('engagement_type', sa.String(length=100), nullable=True),
    sa.Column('body_html', sa.Text(), nullable=False),
    sa.Column('variable_fields', sa.JSON(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_engagement_letter_templates_firm_id'), 'engagement_letter_templates', ['firm_id'], unique=False)
    op.create_table('signature_envelopes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('firm_id', sa.Uuid(), nullable=False),
    sa.Column('client_id', sa.Uuid(), nullable=False),
    sa.Column('engagement_id', sa.Uuid(), nullable=True),
    sa.Column('document_id', sa.Uuid(), nullable=True),
    sa.Column('signed_document_id', sa.Uuid(), nullable=True),
    sa.Column('provider', sa.String(length=50), nullable=False),
    sa.Column('provider_envelope_id', sa.String(length=255), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('signers', sa.JSON(), nullable=False),
    sa.Column('subject', sa.String(length=500), nullable=True),
    sa.Column('message', sa.String(length=2000), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('reminder_count', sa.Integer(), nullable=False),
    sa.Column('last_reminder_sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['signed_document_id'], ['documents.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_signature_envelopes_client_id'), 'signature_envelopes', ['client_id'], unique=False)
    op.create_index(op.f('ix_signature_envelopes_firm_id'), 'signature_envelopes', ['firm_id'], unique=False)
    op.create_index(op.f('ix_signature_envelopes_provider_envelope_id'), 'signature_envelopes', ['provider_envelope_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema — Phase 5: remove signature_envelopes and engagement_letter_templates."""
    op.drop_index(op.f('ix_signature_envelopes_provider_envelope_id'), table_name='signature_envelopes')
    op.drop_index(op.f('ix_signature_envelopes_firm_id'), table_name='signature_envelopes')
    op.drop_index(op.f('ix_signature_envelopes_client_id'), table_name='signature_envelopes')
    op.drop_table('signature_envelopes')
    op.drop_index(op.f('ix_engagement_letter_templates_firm_id'), table_name='engagement_letter_templates')
    op.drop_table('engagement_letter_templates')
