"""add partial unique index on concierge_notifications firm_id trigger_type where unread

Revision ID: e7a179c6f2a1
Revises: 061e12a5cc67
Create Date: 2026-06-21 16:14:15.444404

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7a179c6f2a1'
down_revision: Union[str, Sequence[str], None] = '061e12a5cc67'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ux_concierge_notification_firm_trigger_unread",
        "concierge_notifications",
        ["firm_id", "trigger_type"],
        unique=True,
        postgresql_where=sa.text("is_read = false"),
    )


def downgrade() -> None:
    op.drop_index(
        "ux_concierge_notification_firm_trigger_unread",
        table_name="concierge_notifications",
    )
