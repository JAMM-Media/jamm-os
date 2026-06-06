# migrations/versions/0047_per_staff_integrations.py

"""per staff integrations

Revision ID: 0047_per_staff_integrations
Revises: 0046_add_portal_domain_to_firms
Create Date: 2026-06-06
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0047_per_staff_integrations'
down_revision: Union[str, Sequence[str], None] = '0046_add_portal_domain_to_firms'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'integrations',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_integrations_user_id',
        'integrations',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE',
    )
    op.drop_constraint('uq_integration_firm_provider', 'integrations', type_='unique')
    op.create_unique_constraint(
        'uq_integration_firm_user_provider',
        'integrations',
        ['firm_id', 'user_id', 'provider'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_integration_firm_user_provider', 'integrations', type_='unique')
    op.create_unique_constraint('uq_integration_firm_provider', 'integrations', ['firm_id', 'provider'])
    op.drop_constraint('fk_integrations_user_id', 'integrations', type_='foreignkey')
    op.drop_column('integrations', 'user_id')
