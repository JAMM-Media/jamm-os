# migrations/versions/b1c2d3e4f5a6_fix_triggerevent_enum_to_varchar.py

"""fix triggerevent enum to varchar

Revision ID: b1c2d3e4f5a6
Revises: af413012bb62
Create Date: 2026-03-31

The triggerevent PostgreSQL enum was created with underscore member names
(e.g. 'invoice_created') but the Python TriggerEvent enum has dot-notation
values (e.g. 'invoice.created'). SQLAlchemy serializes the Python values,
causing PostgreSQL to reject them. Fix: convert both trigger_event columns
to VARCHAR and drop the native enum type. SQLAlchemy will use native_enum=False
on the model side, storing the dot-notation strings directly.

The automationexecutionstatus enum has the same issue (values match names so
it works, but for consistency also convert to VARCHAR).
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'af413012bb62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert automation_rules.trigger_event from native enum to VARCHAR
    op.execute(
        "ALTER TABLE automation_rules "
        "ALTER COLUMN trigger_event TYPE VARCHAR "
        "USING trigger_event::TEXT"
    )

    # Convert automation_execution_logs.trigger_event from native enum to VARCHAR
    op.execute(
        "ALTER TABLE automation_execution_logs "
        "ALTER COLUMN trigger_event TYPE VARCHAR "
        "USING trigger_event::TEXT"
    )

    # Convert automation_execution_logs.status from native enum to VARCHAR
    op.execute(
        "ALTER TABLE automation_execution_logs "
        "ALTER COLUMN status TYPE VARCHAR "
        "USING status::TEXT"
    )

    # Drop the now-unused native PostgreSQL enum types
    op.execute("DROP TYPE IF EXISTS triggerevent")
    op.execute("DROP TYPE IF EXISTS automationexecutionstatus")


def downgrade() -> None:
    # Recreate the enum types (with underscore names — original state)
    op.execute(
        "CREATE TYPE triggerevent AS ENUM ("
        "'engagement_created', 'engagement_status_changed', 'engagement_completed', "
        "'engagement_overdue', 'engagement_recurrence_created', "
        "'doc_request_created', 'doc_request_item_uploaded', 'doc_request_completed', "
        "'doc_request_reminder_sent', "
        "'esign_sent', 'esign_signed', 'esign_declined', 'esign_expired', 'esign_reminder_sent', "
        "'invoice_created', 'invoice_sent', 'invoice_paid', 'invoice_overdue', "
        "'time_entry_created', 'task_assigned', 'task_reassigned', "
        "'client_created', 'intake_form_submitted'"
        ")"
    )
    op.execute(
        "CREATE TYPE automationexecutionstatus AS ENUM ("
        "'success', 'failed', 'partial', 'skipped'"
        ")"
    )
    op.execute(
        "ALTER TABLE automation_rules "
        "ALTER COLUMN trigger_event TYPE triggerevent "
        "USING trigger_event::triggerevent"
    )
    op.execute(
        "ALTER TABLE automation_execution_logs "
        "ALTER COLUMN trigger_event TYPE triggerevent "
        "USING trigger_event::triggerevent"
    )
    op.execute(
        "ALTER TABLE automation_execution_logs "
        "ALTER COLUMN status TYPE automationexecutionstatus "
        "USING status::automationexecutionstatus"
    )
