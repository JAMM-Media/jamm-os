# migrations/versions/c2d3e4f5g6h7_add_lead_and_referral_partner_tables.py

"""add lead and referral partner tables

Revision ID: c2d3e4f5g6h7
Revises: (z1a2b3c4d5e6, b1c2d3e4f5g6)
Create Date: 2026-08-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5g6h7'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5g6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create referral_partners and leads tables (CRM contract Section 8)."""
    op.create_table(
        'referral_partners',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_referral_partners_firm_id', 'referral_partners', ['firm_id'])

    op.create_table(
        'leads',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column(
            'stage',
            sa.Enum(
                'identified', 'contacted', 'call_booked', 'proposal', 'won', 'lost',
                name='leadstage', native_enum=False,
            ),
            nullable=False,
            server_default='identified',
        ),
        sa.Column(
            'lost_reason',
            sa.Enum(
                'unqualified', 'unresponsive', 'chose_competitor', 'price', 'timing', 'other',
                name='leadlostreason', native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column(
            'referral_source',
            sa.Enum(
                'client_referral', 'professional_referral', 'returning_client',
                'google_search', 'search_ads', 'social_ads', 'social_media',
                'website', 'association_or_community', 'walk_in',
                'cold_outreach', 'purchased_book', 'other', 'unknown',
                name='referralsource', native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column(
            'source_platform',
            sa.Enum(
                'facebook', 'instagram', 'tiktok', 'linkedin', 'youtube', 'x',
                'google', 'bing', 'nextdoor', 'email', 'phone', 'dm',
                'direct_mail', 'other',
                name='sourceplatform', native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column('utm_campaign', sa.String(length=255), nullable=True),
        sa.Column('utm_source', sa.String(length=255), nullable=True),
        sa.Column('utm_medium', sa.String(length=255), nullable=True),
        sa.Column('utm_content', sa.String(length=255), nullable=True),
        sa.Column('utm_term', sa.String(length=255), nullable=True),
        sa.Column('referring_client_id', sa.Uuid(), nullable=True),
        sa.Column('referral_partner_id', sa.Uuid(), nullable=True),
        sa.Column('service_interest', sa.String(length=100), nullable=True),
        sa.Column('entity_type', sa.String(length=20), nullable=True),
        sa.Column('revenue_band', sa.String(length=50), nullable=True),
        sa.Column('urgency', sa.Text(), nullable=True),
        sa.Column('hot', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column(
            'provenance',
            sa.Enum(
                'crm_lead', 'firm_entered', 'client_reported',
                name='leadprovenance', native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('first_response_time', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['referring_client_id'], ['clients.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['referral_partner_id'], ['referral_partners.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_leads_firm_id', 'leads', ['firm_id'])


def downgrade() -> None:
    """Drop leads and referral_partners tables."""
    op.drop_index('ix_leads_firm_id', table_name='leads')
    op.drop_table('leads')
    op.drop_index('ix_referral_partners_firm_id', table_name='referral_partners')
    op.drop_table('referral_partners')
