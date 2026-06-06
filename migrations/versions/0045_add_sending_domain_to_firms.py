# migrations/versions/0045_add_sending_domain_to_firms.py

"""add sending domain fields to firms

Revision ID: 0045_add_sending_domain_to_firms
Revises: 0044_add_entity_subtype_to_clients
Create Date: 2026-06-06
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0045_add_sending_domain_to_firms'
down_revision: Union[str, Sequence[str], None] = '0044_add_entity_subtype_to_clients'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('firms', sa.Column('sending_domain', sa.String(255), nullable=True))
    op.add_column('firms', sa.Column('sending_domain_postmark_id', sa.Integer(), nullable=True))
    op.add_column('firms', sa.Column('sending_domain_verified', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('firms', sa.Column('sending_domain_dkim_host', sa.String(500), nullable=True))
    op.add_column('firms', sa.Column('sending_domain_dkim_value', sa.String(1000), nullable=True))
    op.add_column('firms', sa.Column('sending_domain_return_path_host', sa.String(500), nullable=True))
    op.add_column('firms', sa.Column('sending_domain_return_path_value', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('firms', 'sending_domain_return_path_value')
    op.drop_column('firms', 'sending_domain_return_path_host')
    op.drop_column('firms', 'sending_domain_dkim_value')
    op.drop_column('firms', 'sending_domain_dkim_host')
    op.drop_column('firms', 'sending_domain_verified')
    op.drop_column('firms', 'sending_domain_postmark_id')
    op.drop_column('firms', 'sending_domain')
