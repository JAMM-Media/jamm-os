"""seed peer_network_announcements_room

Revision ID: t1u2v3w4x5y6
Revises: s1t2u3v4w5x6
Create Date: 2026-08-09 00:00:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 't1u2v3w4x5y6'
down_revision: Union[str, Sequence[str], None] = 's1t2u3v4w5x6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Insert the singleton Announcements room."""
    op.execute(
        sa.text(
            "INSERT INTO peer_network_rooms (id, room_type, name, created_at) "
            "VALUES (:id, :room_type, :name, NOW())"
        ).bindparams(
            sa.bindparam('id', value=str(uuid.uuid4()), type_=sa.Uuid()),
            room_type='announcements',
            name=None,
        )
    )


def downgrade() -> None:
    """Remove the singleton Announcements room."""
    op.execute(
        sa.text("DELETE FROM peer_network_rooms WHERE room_type = 'announcements'")
    )
