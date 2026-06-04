# migrations/versions/0006_task_assigned_to_fk.py

"""Convert tasks.assigned_to from String to FK → users.id

Revision ID: 0006
Revises: 0005_phase1_multitenancy
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005_phase1_multitenancy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old string column and replace with a UUID FK column.
    # Any existing string values cannot be automatically migrated to UUIDs,
    # so the column is dropped and recreated as nullable.
    op.drop_column("tasks", "assigned_to")

    op.add_column(
        "tasks",
        sa.Column(
            "assigned_to",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_tasks_assigned_to", "tasks", ["assigned_to"])


def downgrade() -> None:
    op.drop_index("ix_tasks_assigned_to", table_name="tasks")
    op.drop_column("tasks", "assigned_to")

    op.add_column(
        "tasks",
        sa.Column("assigned_to", sa.String(length=200), nullable=True),
    )
