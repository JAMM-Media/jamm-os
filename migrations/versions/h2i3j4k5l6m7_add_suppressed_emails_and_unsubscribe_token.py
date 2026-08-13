# migrations/versions/h2i3j4k5l6m7_add_suppressed_emails_and_unsubscribe_token.py

"""add suppressed_emails table and unsubscribe token columns on enrollments

Revision ID: h2i3j4k5l6m7
Revises: g2h3i4j5k6l7
Create Date: 2026-08-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'h2i3j4k5l6m7'
down_revision: Union[str, Sequence, None] = 'g2h3i4j5k6l7'
branch_labels: Union[str, Sequence, None] = None
depends_on: Union[str, Sequence, None] = None


def upgrade() -> None:
    """Create suppressed_emails and add unsubscribe token columns to enrollments."""
    op.create_table(
        'suppressed_emails',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('reason', sa.String(length=50), nullable=True),
        sa.Column('suppressed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('firm_id', 'email', name='uq_suppressed_email_firm'),
    )
    op.create_index('ix_suppressed_emails_firm_id', 'suppressed_emails', ['firm_id'])

    op.add_column(
        'enrollments',
        sa.Column('unsubscribe_token_hash', sa.String(length=64), nullable=True),
    )
    op.add_column(
        'enrollments',
        sa.Column('unsubscribe_token_expires_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        'ix_enrollments_unsubscribe_token_hash',
        'enrollments',
        ['unsubscribe_token_hash'],
    )


def downgrade() -> None:
    """Reverse suppressed_emails and unsubscribe token columns."""
    op.drop_index('ix_enrollments_unsubscribe_token_hash', table_name='enrollments')
    op.drop_column('enrollments', 'unsubscribe_token_expires_at')
    op.drop_column('enrollments', 'unsubscribe_token_hash')
    op.drop_index('ix_suppressed_emails_firm_id', table_name='suppressed_emails')
    op.drop_table('suppressed_emails')
