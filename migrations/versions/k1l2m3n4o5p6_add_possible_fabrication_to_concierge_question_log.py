"""add_possible_fabrication_to_concierge_question_log

Revision ID: k1l2m3n4o5p6
Revises: j1k2l3m4n5o6
Create Date: 2026-07-22

"""

from alembic import op
import sqlalchemy as sa

revision = "k1l2m3n4o5p6"
down_revision = "j1k2l3m4n5o6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "concierge_question_logs",
        sa.Column("possible_fabrication", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index(
        "ix_concierge_question_log_possible_fabrication",
        "concierge_question_logs",
        ["possible_fabrication"],
    )


def downgrade() -> None:
    op.drop_index("ix_concierge_question_log_possible_fabrication", table_name="concierge_question_logs")
    op.drop_column("concierge_question_logs", "possible_fabrication")
