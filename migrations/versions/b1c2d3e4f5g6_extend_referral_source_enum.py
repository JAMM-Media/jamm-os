# migrations/versions/b1c2d3e4f5g6_extend_referral_source_enum.py

"""extend referral source enum with six crm acquisition values

Revision ID: b1c2d3e4f5g6
Revises: z1a2b3c4d5e6
Create Date: 2026-08-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5g6'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_ENUM = sa.Enum(
    'client_referral', 'professional_referral', 'google_search',
    'social_media', 'website', 'association_or_community',
    'walk_in', 'other',
    name='referralsource', native_enum=False,
)

_NEW_ENUM = sa.Enum(
    'client_referral', 'professional_referral', 'returning_client',
    'google_search', 'search_ads', 'social_ads', 'social_media',
    'website', 'association_or_community', 'walk_in',
    'cold_outreach', 'purchased_book', 'other', 'unknown',
    name='referralsource', native_enum=False,
)


def upgrade() -> None:
    """Add six new acquisition-tracking values to ReferralSource (CRM contract Section 3.2)."""
    op.alter_column(
        'clients',
        'referral_source',
        type_=_NEW_ENUM,
        existing_type=_OLD_ENUM,
        existing_nullable=True,
    )


def downgrade() -> None:
    """Revert ReferralSource to the original eight values."""
    op.alter_column(
        'clients',
        'referral_source',
        type_=_OLD_ENUM,
        existing_type=_NEW_ENUM,
        existing_nullable=True,
    )
