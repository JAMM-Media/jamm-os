# migrations/versions/e06c341c7b5a_add_client_referral_source_and_firm_.py

"""add client referral source and firm signup source

Revision ID: e06c341c7b5a
Revises: 0057_add_request_id_to_behavioral_events
Create Date: 2026-07-02 00:49:09.830703

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e06c341c7b5a'
down_revision: Union[str, Sequence[str], None] = '0057_add_request_id_to_behavioral_events'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'clients',
        sa.Column(
            'referral_source',
            sa.Enum(
                'client_referral', 'professional_referral', 'google_search',
                'social_media', 'website', 'association_or_community',
                'walk_in', 'other',
                name='referralsource', native_enum=False,
            ),
            nullable=True,
        ),
    )
    op.add_column('clients', sa.Column('referring_client_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_clients_referring_client_id_clients',
        'clients', 'clients',
        ['referring_client_id'], ['id'],
        ondelete='SET NULL',
    )
    op.add_column('firms', sa.Column('signup_source', sa.String(length=100), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('firms', 'signup_source')
    op.drop_constraint('fk_clients_referring_client_id_clients', 'clients', type_='foreignkey')
    op.drop_column('clients', 'referring_client_id')
    op.drop_column('clients', 'referral_source')
