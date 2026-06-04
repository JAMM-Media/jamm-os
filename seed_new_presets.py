from dotenv import load_dotenv
load_dotenv()

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.db.session import SessionLocal
from app.models.automation_rule import AutomationRule
from sqlalchemy import text

FIRM_ID = UUID("094716a4-279b-41ad-b671-5c750818e7ca")

new_presets = [
    {
        "name": "1040 Season Kickoff",
        "description": "Sends welcome email and creates intake tasks when a 1040 engagement is opened.",
        "is_enabled": False,
        "trigger_event": "engagement.created",
        "trigger_conditions": [],
        "actions": [
            {"type": "send_email", "config": {"template": "client_welcome"}, "order": 0},
            {"type": "create_task", "config": {"title": "Collect prior year return"}, "order": 1},
            {"type": "create_task", "config": {"title": "Verify contact info and entity type"}, "order": 2},
        ],
    },
    {
        "name": "Extension Filed Auto-Notify",
        "description": "Notifies client of extension, creates deadline task, and updates engagement status.",
        "is_enabled": True,
        "trigger_event": "extension.filed",
        "trigger_conditions": [],
        "actions": [
            {"type": "send_email", "config": {"template": "extension_confirmation"}, "order": 0},
            {"type": "create_task", "config": {"title": "Prepare return by extended deadline"}, "order": 1},
        ],
    },
    {
        "name": "IRS Authorization Expiry Warning",
        "description": "Alerts staff and client when an IRS authorization is approaching expiry.",
        "is_enabled": True,
        "trigger_event": "irs_authorization.expiry_approaching",
        "trigger_conditions": [],
        "actions": [
            {"type": "send_notification", "config": {"to": "staff"}, "order": 0},
            {"type": "create_task", "config": {"title": "Renew Form 8821/2848 before expiry"}, "order": 1},
            {"type": "send_email", "config": {"template": "irs_auth_expiry_warning"}, "order": 2},
        ],
    },
    {
        "name": "Invoice Overdue Escalating Sequence",
        "description": "Sends escalating payment reminders on day 1, day 7, and notifies firm owner on day 14.",
        "is_enabled": True,
        "trigger_event": "invoice.overdue",
        "trigger_conditions": [],
        "actions": [
            {"type": "send_email", "config": {"template": "invoice_overdue_reminder", "delay_days": 1}, "order": 0},
            {"type": "send_email", "config": {"template": "invoice_overdue_followup", "delay_days": 7}, "order": 1},
            {"type": "send_notification", "config": {"to": "firm_owner", "delay_days": 14}, "order": 2},
        ],
    },
    {
        "name": "Engagement Deadline Approaching — 14-day Alert",
        "description": "Notifies assigned staff 14 days before an engagement deadline.",
        "is_enabled": True,
        "trigger_event": "engagement.deadline_approaching",
        "trigger_conditions": [],
        "actions": [
            {"type": "send_notification", "config": {"to": "assigned_staff", "message": "Engagement deadline in 14 days — check task count"}, "order": 0},
        ],
    },
    {
        "name": "Return Completed: Client Delivery Loop",
        "description": "Creates delivery task, generates invoice, and notifies client when a return is complete.",
        "is_enabled": False,
        "trigger_event": "engagement.completed",
        "trigger_conditions": [],
        "actions": [
            {"type": "create_task", "config": {"title": "Upload final return to client portal"}, "order": 0},
            {"type": "create_invoice", "config": {"source": "time_entries"}, "order": 1},
            {"type": "send_email", "config": {"template": "return_ready"}, "order": 2},
            {"type": "create_task", "config": {"title": "Confirm client acknowledgment within 5 days"}, "order": 3},
        ],
    },
    {
        "name": "New Client Full Onboarding Sequence",
        "description": "Sends welcome email, creates onboarding tasks, and sends intake document request for new clients.",
        "is_enabled": False,
        "trigger_event": "client.created",
        "trigger_conditions": [],
        "actions": [
            {"type": "send_email", "config": {"template": "client_portal_welcome"}, "order": 0},
            {"type": "create_task", "config": {"title": "Schedule onboarding call"}, "order": 1},
            {"type": "create_task", "config": {"title": "Collect entity documents"}, "order": 2},
        ],
    },
]

db = SessionLocal()
try:
    now = datetime.now(timezone.utc)
    for preset in new_presets:
        result = db.execute(
            text(
                "SELECT COUNT(*) FROM automation_rules "
                "WHERE firm_id=:firm_id AND name=:name"
            ),
            {"firm_id": str(FIRM_ID), "name": preset["name"]},
        ).scalar()
        if result > 0:
            print(f"{preset['name']} — skipped (already exists)")
        else:
            rule = AutomationRule(
                id=uuid4(),
                firm_id=FIRM_ID,
                name=preset["name"],
                description=preset["description"],
                is_enabled=preset["is_enabled"],
                trigger_event=preset["trigger_event"],
                trigger_conditions=preset["trigger_conditions"],
                actions=preset["actions"],
                execution_count=0,
                last_executed_at=None,
                created_at=now,
                updated_at=now,
            )
            db.add(rule)
            print(f"{preset['name']} — inserted")
    db.commit()
finally:
    db.close()
