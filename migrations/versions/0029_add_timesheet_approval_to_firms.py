"""add timesheet_approval_required to firms

Revision ID: 0029_add_timesheet_approval_to_firms
Revises: 0028_add_timesheet_fields_to_time_entries
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0029_add_timesheet_approval_to_firms'
down_revision: Union[str, Sequence[str], None] = '0028_add_timesheet_fields_to_time_entries'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'firms',
        sa.Column(
            'timesheet_approval_required',
            sa.Boolean(),
            nullable=False,
            server_default='false',
        ),
    )


def downgrade() -> None:
    op.drop_column('firms', 'timesheet_approval_required')
