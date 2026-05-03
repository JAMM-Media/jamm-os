"""add_staff_refresh_token_fields

Revision ID: b58c35fa26bc
Revises: b9bb8c75b9bd
Create Date: 2026-04-30 11:47:07.730326

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b58c35fa26bc'
down_revision: Union[str, Sequence[str], None] = 'b9bb8c75b9bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('staff_refresh_token_hash', sa.String(length=64), nullable=True))
    op.add_column('users', sa.Column('staff_refresh_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_users_staff_refresh_token_hash'), 'users', ['staff_refresh_token_hash'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_staff_refresh_token_hash'), table_name='users')
    op.drop_column('users', 'staff_refresh_expires_at')
    op.drop_column('users', 'staff_refresh_token_hash')
