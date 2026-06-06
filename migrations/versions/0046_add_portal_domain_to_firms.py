# migrations/versions/0046_add_portal_domain_to_firms.py

"""add portal domain fields to firms

Revision ID: 0046_add_portal_domain_to_firms
Revises: 0045_add_sending_domain_to_firms
Create Date: 2026-06-06
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0046_add_portal_domain_to_firms'
down_revision: Union[str, Sequence[str], None] = '0045_add_sending_domain_to_firms'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('firms', sa.Column('portal_domain', sa.String(255), nullable=True))
    op.add_column('firms', sa.Column('portal_domain_verified', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('firms', sa.Column('portal_domain_verification_token', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('firms', 'portal_domain_verification_token')
    op.drop_column('firms', 'portal_domain_verified')
    op.drop_column('firms', 'portal_domain')
