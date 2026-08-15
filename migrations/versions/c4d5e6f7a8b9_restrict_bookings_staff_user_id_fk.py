# migrations/versions/c4d5e6f7a8b9_restrict_bookings_staff_user_id_fk.py

"""restrict bookings staff_user_id fk

Revision ID: c4d5e6f7a8b9
Revises: b7f3a2c1d9e8
Create Date: 2026-08-15

Changes bookings.staff_user_id FK from ON DELETE SET NULL to ON DELETE RESTRICT.

A staff member with booking history cannot be deleted outright. The intelligence
layer needs to trace historical meeting performance back to a specific staff member
even after they leave the firm. Deletion is blocked; a real off-boarding path
(not yet built) that reassigns or archives booking history first is required.

lead_id is unchanged -- it keeps ON DELETE SET NULL per original design.
"""

from typing import Sequence, Union

from alembic import op


revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b7f3a2c1d9e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        'bookings_staff_user_id_fkey',
        'bookings',
        type_='foreignkey',
    )
    op.create_foreign_key(
        'bookings_staff_user_id_fkey',
        'bookings',
        'users',
        ['staff_user_id'],
        ['id'],
        ondelete='RESTRICT',
    )


def downgrade() -> None:
    op.drop_constraint(
        'bookings_staff_user_id_fkey',
        'bookings',
        type_='foreignkey',
    )
    op.create_foreign_key(
        'bookings_staff_user_id_fkey',
        'bookings',
        'users',
        ['staff_user_id'],
        ['id'],
        ondelete='SET NULL',
    )
