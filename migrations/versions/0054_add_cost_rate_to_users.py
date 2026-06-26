# migrations/versions/0054_add_cost_rate_to_users.py

"""add cost_rate to users

Revision ID: 0054_add_cost_rate_to_users
Revises: 0053_add_staff_credential_and_cpe_record_models
Create Date: 2026-06-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0054_add_cost_rate_to_users'
down_revision: Union[str, Sequence[str], None] = '0053_add_staff_credential_and_cpe_record_models'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('cost_rate', sa.Numeric(10, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'cost_rate')
