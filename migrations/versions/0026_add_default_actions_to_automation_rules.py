"""add default_actions to automation_rules

Revision ID: 0026_add_default_actions_to_automation_rules
Revises: 0025_add_index_consent_to_firms
Create Date: 2026-05-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '0026_add_default_actions_to_automation_rules'
down_revision: Union[str, Sequence[str], None] = '0025_add_index_consent_to_firms'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'automation_rules',
        sa.Column(
            'default_actions',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    # Backfill existing rows: copy actions → default_actions
    op.execute(
        """
        UPDATE automation_rules
        SET default_actions = actions
        WHERE default_actions::text = '[]'
           OR default_actions IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column('automation_rules', 'default_actions')
