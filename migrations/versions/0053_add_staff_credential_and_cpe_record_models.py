# migrations/versions/0053_add_staff_credential_and_cpe_record_models.py

"""add staff credential and cpe record models

Revision ID: 0053_add_staff_credential_and_cpe_record_models
Revises: 061e12a5cc67
Create Date: 2026-06-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0053_add_staff_credential_and_cpe_record_models'
down_revision: Union[str, Sequence[str], None] = '061e12a5cc67'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'staff_credentials',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('firm_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column(
            'credential_type',
            sa.Enum(
                'cpa_license', 'ea_enrollment', 'ptin', 'state_license', 'other',
                name='credentialtype',
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('credential_number', sa.String(100), nullable=True),
        sa.Column('state', sa.String(50), nullable=True),
        sa.Column('issued_at', sa.Date(), nullable=True),
        sa.Column('expires_at', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_staff_credentials_firm_id', 'staff_credentials', ['firm_id'])
    op.create_index('ix_staff_credentials_user_id', 'staff_credentials', ['user_id'])

    op.create_table(
        'cpe_records',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('firm_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('reporting_period_start', sa.Date(), nullable=False),
        sa.Column('reporting_period_end', sa.Date(), nullable=False),
        sa.Column('hours_required', sa.Numeric(6, 2), nullable=False),
        sa.Column('hours_completed', sa.Numeric(6, 2), nullable=False, server_default='0'),
        sa.Column('deadline', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_cpe_records_firm_id', 'cpe_records', ['firm_id'])
    op.create_index('ix_cpe_records_user_id', 'cpe_records', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_cpe_records_user_id', table_name='cpe_records')
    op.drop_index('ix_cpe_records_firm_id', table_name='cpe_records')
    op.drop_table('cpe_records')

    op.drop_index('ix_staff_credentials_user_id', table_name='staff_credentials')
    op.drop_index('ix_staff_credentials_firm_id', table_name='staff_credentials')
    op.drop_table('staff_credentials')
