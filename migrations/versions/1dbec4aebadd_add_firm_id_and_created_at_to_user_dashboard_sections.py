"""add firm_id and created_at to user_dashboard_sections

Revision ID: 1dbec4aebadd
Revises: 1cdc9c33705a
Create Date: 2026-09-26 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '1dbec4aebadd'
down_revision: Union[str, Sequence[str], None] = '1cdc9c33705a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add firm_id as nullable first so we can backfill
    op.add_column(
        'user_dashboard_sections',
        sa.Column('firm_id', sa.UUID(), nullable=True),
    )
    # Add created_at with a server default so existing rows get a value
    op.add_column(
        'user_dashboard_sections',
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text('now()'),
        ),
    )

    # Backfill firm_id from the users table
    op.execute(
        """
        UPDATE user_dashboard_sections
        SET firm_id = users.firm_id
        FROM users
        WHERE users.id = user_dashboard_sections.user_id
        """
    )

    # Promote firm_id to NOT NULL
    op.alter_column('user_dashboard_sections', 'firm_id', nullable=False)

    # Promote created_at to NOT NULL
    op.alter_column('user_dashboard_sections', 'created_at', nullable=False)

    # Add FK constraint and index
    op.create_foreign_key(
        'fk_user_dashboard_sections_firm_id',
        'user_dashboard_sections',
        'firms',
        ['firm_id'],
        ['id'],
        ondelete='CASCADE',
    )
    op.create_index(
        'ix_user_dashboard_sections_firm_id',
        'user_dashboard_sections',
        ['firm_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_user_dashboard_sections_firm_id', table_name='user_dashboard_sections')
    op.drop_constraint(
        'fk_user_dashboard_sections_firm_id',
        'user_dashboard_sections',
        type_='foreignkey',
    )
    op.drop_column('user_dashboard_sections', 'firm_id')
    op.drop_column('user_dashboard_sections', 'created_at')
