# /home/corby/jamm-os/migrations/versions/0052_set_concierge_active_default_true.py
"""set concierge_active default true

Revision ID: 0052_set_concierge_active_default_true
Revises: 0051_add_metadata_to_concierge_notifications
Create Date: 2026-06-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0052_set_concierge_active_default_true'
down_revision: Union[str, Sequence[str], None] = '0051_add_metadata_to_concierge_notifications'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('firms', 'concierge_active',
        server_default='true',
        existing_type=sa.Boolean(),
        existing_nullable=False)


def downgrade() -> None:
    op.alter_column('firms', 'concierge_active',
        server_default='false',
        existing_type=sa.Boolean(),
        existing_nullable=False)
