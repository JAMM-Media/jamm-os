"""add_intake_answer_and_lead_intake_token

Revision ID: f8e2a9b7c4d1
Revises: ce1f48a31ce8
Create Date: 2026-09-03 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'f8e2a9b7c4d1'
down_revision = 'ce1f48a31ce8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # intake_answers: append-only fact table for every intake answer
    op.create_table(
        'intake_answers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('firm_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('firms.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lead_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', sa.Enum(
            'flag', 'dimension_numeric', 'dimension_categorical', 'dimension_boolean',
            name='intakeanswerkind', native_enum=False,
        ), nullable=False),
        sa.Column('dimension_key', sa.String(100), nullable=True),
        sa.Column('value_option_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('value_numeric', sa.Numeric(18, 4), nullable=True),
        sa.Column('value_boolean', sa.Boolean(), nullable=True),
        sa.Column('value_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_intake_answers_firm_id', 'intake_answers', ['firm_id'])
    op.create_index('ix_intake_answers_lead_id', 'intake_answers', ['lead_id'])

    # lead_intake_tokens: short-lived, non-single-use tokens for intake continuation
    op.create_table(
        'lead_intake_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('firm_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('firms.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lead_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_lead_intake_tokens_firm_id', 'lead_intake_tokens', ['firm_id'])
    op.create_index('ix_lead_intake_tokens_lead_id', 'lead_intake_tokens', ['lead_id'])
    op.create_index('ix_lead_intake_tokens_token_hash', 'lead_intake_tokens', ['token_hash'],
                    unique=True)


def downgrade() -> None:
    op.drop_index('ix_lead_intake_tokens_token_hash', table_name='lead_intake_tokens')
    op.drop_index('ix_lead_intake_tokens_lead_id', table_name='lead_intake_tokens')
    op.drop_index('ix_lead_intake_tokens_firm_id', table_name='lead_intake_tokens')
    op.drop_table('lead_intake_tokens')

    op.drop_index('ix_intake_answers_lead_id', table_name='intake_answers')
    op.drop_index('ix_intake_answers_firm_id', table_name='intake_answers')
    op.drop_table('intake_answers')

    op.execute("DROP TYPE IF EXISTS intakeanswerkind")
