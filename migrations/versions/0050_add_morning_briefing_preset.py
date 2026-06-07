# migrations/versions/0050_add_morning_briefing_preset.py

"""add_morning_briefing_preset

Revision ID: 0050_add_morning_briefing_preset
Revises: 0049_add_briefing_sent_at_to_firms
Create Date: 2026-06-06

"""
from typing import Sequence, Union
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = '0050_add_morning_briefing_preset'
down_revision: Union[str, Sequence[str], None] = '0049_add_briefing_sent_at_to_firms'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    firm_ids = conn.execute(text("SELECT id FROM firms")).fetchall()
    now = datetime.now(timezone.utc)
    for (firm_id,) in firm_ids:
        existing = conn.execute(
            text(
                "SELECT id FROM automation_rules "
                "WHERE firm_id = :firm_id AND trigger_event = 'morning_briefing'"
            ),
            {"firm_id": str(firm_id)},
        ).fetchone()
        if existing:
            continue
        conn.execute(
            text(
                "INSERT INTO automation_rules "
                "(id, firm_id, name, description, is_enabled, trigger_event, "
                "trigger_conditions, actions, default_actions, execution_count, "
                "created_at, updated_at) "
                "VALUES (:id, :firm_id, :name, :description, :is_enabled, :trigger_event, "
                "'[]'::jsonb, '[]'::jsonb, '[]'::jsonb, 0, :created_at, :updated_at)"
            ),
            {
                "id": str(uuid.uuid4()),
                "firm_id": str(firm_id),
                "name": "Morning Briefing",
                "description": (
                    "Get a daily summary of your firm's current engagement status, "
                    "incomplete items, and upcoming due dates when you open the dashboard each morning."
                ),
                "is_enabled": False,
                "trigger_event": "morning_briefing",
                "created_at": now,
                "updated_at": now,
            },
        )


def downgrade() -> None:
    op.execute(text("DELETE FROM automation_rules WHERE trigger_event = 'morning_briefing'"))
