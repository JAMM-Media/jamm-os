# app/services/automation_presets.py

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models.automation_rule import AutomationRule
from app.core.enums import TriggerEvent, AutomationActionType

logger = logging.getLogger(__name__)


def seed_firm_presets(firm_id: UUID, db: Session) -> int:
    presets = _get_preset_rules(firm_id)
    for preset in presets:
        rule = AutomationRule(**preset)
        db.add(rule)
    db.commit()
    logger.info(f"Seeded {len(presets)} automation presets for firm {firm_id}")
    return len(presets)


def _get_preset_rules(firm_id: UUID) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)

    return [
        # PRESET 1 — Document Request Reminder
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "Document Request Reminder (3-day)",
            "description": (
                "Sends a reminder to the client 3 days after a document request is created "
                "if it is still pending"
            ),
            "is_enabled": True,
            "trigger_event": TriggerEvent.doc_request_created,
            "trigger_conditions": [],
            "actions": [
                {
                    "type": AutomationActionType.send_email,
                    "config": {
                        "to": "client",
                        "subject": "Reminder: Documents needed",
                        "template": "doc_request_reminder",
                        "delay_days": 3,
                    },
                    "order": 0,
                }
            ],
            "default_actions": [
                {
                    "type": AutomationActionType.send_email,
                    "config": {
                        "to": "client",
                        "subject": "Reminder: Documents needed",
                        "template": "doc_request_reminder",
                        "delay_days": 3,
                    },
                    "order": 0,
                }
            ],  # exact copy of actions above
            "execution_count": 0,
            "last_executed_at": None,
            "created_at": now,
            "updated_at": now,
        },
        # PRESET 2 — E-Signature Reminder
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "E-Signature Reminder (2-day)",
            "description": (
                "Sends a reminder to the client 2 days after an engagement letter is sent "
                "for signature if not yet signed"
            ),
            "is_enabled": True,
            "trigger_event": TriggerEvent.esign_sent,
            "trigger_conditions": [],
            "actions": [
                {
                    "type": AutomationActionType.send_email,
                    "config": {
                        "to": "client",
                        "subject": "Reminder: Signature needed",
                        "template": "esign_reminder",
                        "delay_days": 2,
                    },
                    "order": 0,
                }
            ],
            "default_actions": [
                {
                    "type": AutomationActionType.send_email,
                    "config": {
                        "to": "client",
                        "subject": "Reminder: Signature needed",
                        "template": "esign_reminder",
                        "delay_days": 2,
                    },
                    "order": 0,
                }
            ],  # exact copy of actions above
            "execution_count": 0,
            "last_executed_at": None,
            "created_at": now,
            "updated_at": now,
        },
        # PRESET 3 — Overdue Task Alert to Staff
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "Overdue Task Alert to Staff",
            "description": "Notifies the assigned staff member when a task becomes overdue",
            "is_enabled": True,
            "trigger_event": TriggerEvent.task_assigned,
            "trigger_conditions": [],
            "actions": [
                {
                    "type": AutomationActionType.send_notification,
                    "config": {
                        "to": "assigned_staff",
                        "message": "A task assigned to you is now overdue",
                        "notification_type": "task_overdue",
                    },
                    "order": 0,
                }
            ],
            "default_actions": [
                {
                    "type": AutomationActionType.send_notification,
                    "config": {
                        "to": "assigned_staff",
                        "message": "A task assigned to you is now overdue",
                        "notification_type": "task_overdue",
                    },
                    "order": 0,
                }
            ],  # exact copy of actions above
            "execution_count": 0,
            "last_executed_at": None,
            "created_at": now,
            "updated_at": now,
        },
        # PRESET 4 — Engagement Completed → Create Invoice
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "Auto-Create Invoice on Engagement Completion",
            "description": (
                "Automatically creates a draft invoice when an engagement is marked as completed"
            ),
            "is_enabled": False,
            "trigger_event": TriggerEvent.engagement_completed,
            "trigger_conditions": [],
            "actions": [
                {
                    "type": AutomationActionType.create_invoice,
                    "config": {
                        "line_items": [
                            {
                                "description": "Professional Services",
                                "quantity": 1,
                                "unit_price": 0,
                            }
                        ],
                        "due_days_from_now": 30,
                    },
                    "order": 0,
                }
            ],
            "default_actions": [
                {
                    "type": AutomationActionType.create_invoice,
                    "config": {
                        "line_items": [
                            {
                                "description": "Professional Services",
                                "quantity": 1,
                                "unit_price": 0,
                            }
                        ],
                        "due_days_from_now": 30,
                    },
                    "order": 0,
                }
            ],  # exact copy of actions above
            "execution_count": 0,
            "last_executed_at": None,
            "created_at": now,
            "updated_at": now,
        },
        # PRESET 5 — New Client Welcome Email
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "New Client Welcome Email",
            "description": (
                "Sends a welcome email to the client when they are first added to the system"
            ),
            "is_enabled": True,
            "trigger_event": TriggerEvent.client_created,
            "trigger_conditions": [],
            "actions": [
                {
                    "type": AutomationActionType.send_email,
                    "config": {
                        "to": "client",
                        "subject": "Welcome — we're glad to have you",
                        "template": "client_welcome",
                    },
                    "order": 0,
                }
            ],
            "default_actions": [
                {
                    "type": AutomationActionType.send_email,
                    "config": {
                        "to": "client",
                        "subject": "Welcome — we're glad to have you",
                        "template": "client_welcome",
                    },
                    "order": 0,
                }
            ],  # exact copy of actions above
            "execution_count": 0,
            "last_executed_at": None,
            "created_at": now,
            "updated_at": now,
        },
        # PRESET 6 — Document Request Complete → Notify Staff
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "Notify Staff When Documents Are Complete",
            "description": (
                "Notifies the assigned staff member when a client finishes uploading "
                "all requested documents"
            ),
            "is_enabled": False,
            "trigger_event": TriggerEvent.doc_request_completed,
            "trigger_conditions": [],
            "actions": [
                {
                    "type": AutomationActionType.send_notification,
                    "config": {
                        "to": "assigned_staff",
                        "message": "Client has uploaded all requested documents",
                        "notification_type": "doc_request_completed",
                    },
                    "order": 0,
                }
            ],
            "default_actions": [
                {
                    "type": AutomationActionType.send_notification,
                    "config": {
                        "to": "assigned_staff",
                        "message": "Client has uploaded all requested documents",
                        "notification_type": "doc_request_completed",
                    },
                    "order": 0,
                }
            ],  # exact copy of actions above
            "execution_count": 0,
            "last_executed_at": None,
            "created_at": now,
            "updated_at": now,
        },
        # PRESET 7 — Invoice Overdue Reminder
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "Invoice Overdue Reminder",
            "description": "Sends a payment reminder to the client when an invoice becomes overdue",
            "is_enabled": True,
            "trigger_event": TriggerEvent.invoice_overdue,
            "trigger_conditions": [],
            "actions": [
                {
                    "type": AutomationActionType.send_email,
                    "config": {
                        "to": "client",
                        "subject": "Invoice payment overdue",
                        "template": "invoice_overdue_reminder",
                    },
                    "order": 0,
                }
            ],
            "default_actions": [
                {
                    "type": AutomationActionType.send_email,
                    "config": {
                        "to": "client",
                        "subject": "Invoice payment overdue",
                        "template": "invoice_overdue_reminder",
                    },
                    "order": 0,
                }
            ],  # exact copy of actions above
            "execution_count": 0,
            "last_executed_at": None,
            "created_at": now,
            "updated_at": now,
        },
        # PRESET 8 — Recurring Engagement Kickoff
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "Recurring Engagement Kickoff Notification",
            "description": (
                "Notifies the assigned staff member when a new recurring engagement "
                "is automatically created"
            ),
            "is_enabled": False,
            "trigger_event": TriggerEvent.engagement_recurrence_created,
            "trigger_conditions": [],
            "actions": [
                {
                    "type": AutomationActionType.send_notification,
                    "config": {
                        "to": "assigned_staff",
                        "message": "A new recurring engagement has been created and is ready for review",
                        "notification_type": "recurring_engagement_created",
                    },
                    "order": 0,
                }
            ],
            "default_actions": [
                {
                    "type": AutomationActionType.send_notification,
                    "config": {
                        "to": "assigned_staff",
                        "message": "A new recurring engagement has been created and is ready for review",
                        "notification_type": "recurring_engagement_created",
                    },
                    "order": 0,
                }
            ],  # exact copy of actions above
            "execution_count": 0,
            "last_executed_at": None,
            "created_at": now,
            "updated_at": now,
        },
        # PRESET 9 — 1040 Season Kickoff
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "1040 Season Kickoff",
            "description": (
                "Sends welcome email and creates intake tasks when a 1040 engagement is opened."
            ),
            "is_enabled": False,
            "trigger_event": TriggerEvent.engagement_created,
            "trigger_conditions": [],
            "actions": [
                {
                    "type": AutomationActionType.send_email,
                    "config": {"template": "client_welcome"},
                    "order": 0,
                },
                {
                    "type": AutomationActionType.create_task,
                    "config": {"title": "Collect prior year return"},
                    "order": 1,
                },
                {
                    "type": AutomationActionType.create_task,
                    "config": {"title": "Verify contact info and entity type"},
                    "order": 2,
                },
            ],
            "default_actions": [
                {
                    "type": AutomationActionType.send_email,
                    "config": {"template": "client_welcome"},
                    "order": 0,
                },
                {
                    "type": AutomationActionType.create_task,
                    "config": {"title": "Collect prior year return"},
                    "order": 1,
                },
                {
                    "type": AutomationActionType.create_task,
                    "config": {"title": "Verify contact info and entity type"},
                    "order": 2,
                },
            ],  # exact copy of actions above
            "execution_count": 0,
            "last_executed_at": None,
            "created_at": now,
            "updated_at": now,
        },
        # PRESET 10 — Extension Filed Auto-Notify
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "Extension Filed Auto-Notify",
            "description": (
                "Notifies client of extension, creates deadline task, and updates engagement status."
            ),
            "is_enabled": True,
            "trigger_event": TriggerEvent.extension_filed,
            "trigger_conditions": [],
            "actions": [
                {
                    "type": AutomationActionType.send_email,
                    "config": {"template": "extension_confirmation"},
                    "order": 0,
                },
                {
                    "type": AutomationActionType.create_task,
                    "config": {"title": "Prepare return by extended deadline"},
                    "order": 1,
                },
            ],
            "default_actions": [
                {
                    "type": AutomationActionType.send_email,
                    "config": {"template": "extension_confirmation"},
                    "order": 0,
                },
                {
                    "type": AutomationActionType.create_task,
                    "config": {"title": "Prepare return by extended deadline"},
                    "order": 1,
                },
            ],  # exact copy of actions above
            "execution_count": 0,
            "last_executed_at": None,
            "created_at": now,
            "updated_at": now,
        },
        # PRESET 11 — IRS Authorization Expiry Warning
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "IRS Authorization Expiry Warning",
            "description": (
                "Alerts staff and client when an IRS authorization is approaching expiry."
            ),
            "is_enabled": True,
            "trigger_event": TriggerEvent.irs_authorization_expiry_approaching,
            "trigger_conditions": [],
            "actions": [
                {
                    "type": AutomationActionType.send_notification,
                    "config": {"to": "staff"},
                    "order": 0,
                },
                {
                    "type": AutomationActionType.create_task,
                    "config": {"title": "Renew Form 8821/2848 before expiry"},
                    "order": 1,
                },
                {
                    "type": AutomationActionType.send_email,
                    "config": {"template": "irs_auth_expiry_warning"},
                    "order": 2,
                },
            ],
            "default_actions": [
                {
                    "type": AutomationActionType.send_notification,
                    "config": {"to": "staff"},
                    "order": 0,
                },
                {
                    "type": AutomationActionType.create_task,
                    "config": {"title": "Renew Form 8821/2848 before expiry"},
                    "order": 1,
                },
                {
                    "type": AutomationActionType.send_email,
                    "config": {"template": "irs_auth_expiry_warning"},
                    "order": 2,
                },
            ],  # exact copy of actions above
            "execution_count": 0,
            "last_executed_at": None,
            "created_at": now,
            "updated_at": now,
        },
        # PRESET 12 — Invoice Overdue Escalating Sequence
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "Invoice Overdue Escalating Sequence",
            "description": (
                "Sends escalating payment reminders on day 1, day 7, "
                "and notifies firm owner on day 14."
            ),
            "is_enabled": True,
            "trigger_event": TriggerEvent.invoice_overdue,
            "trigger_conditions": [],
            "actions": [
                {
                    "type": AutomationActionType.send_email,
                    "config": {"template": "invoice_overdue_reminder", "delay_days": 1},
                    "order": 0,
                },
                {
                    "type": AutomationActionType.send_email,
                    "config": {"template": "invoice_overdue_followup", "delay_days": 7},
                    "order": 1,
                },
                {
                    "type": AutomationActionType.send_notification,
                    "config": {"to": "firm_owner", "delay_days": 14},
                    "order": 2,
                },
            ],
            "default_actions": [
                {
                    "type": AutomationActionType.send_email,
                    "config": {"template": "invoice_overdue_reminder", "delay_days": 1},
                    "order": 0,
                },
                {
                    "type": AutomationActionType.send_email,
                    "config": {"template": "invoice_overdue_followup", "delay_days": 7},
                    "order": 1,
                },
                {
                    "type": AutomationActionType.send_notification,
                    "config": {"to": "firm_owner", "delay_days": 14},
                    "order": 2,
                },
            ],  # exact copy of actions above
            "execution_count": 0,
            "last_executed_at": None,
            "created_at": now,
            "updated_at": now,
        },
        # PRESET 13 — Engagement Deadline Approaching — 14-day Alert
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "Engagement Deadline Approaching — 14-day Alert",
            "description": "Notifies assigned staff 14 days before an engagement deadline.",
            "is_enabled": True,
            "trigger_event": TriggerEvent.engagement_deadline_approaching,
            "trigger_conditions": [],
            "actions": [
                {
                    "type": AutomationActionType.send_notification,
                    "config": {
                        "to": "assigned_staff",
                        "message": "Engagement deadline in 14 days — check task count",
                    },
                    "order": 0,
                },
            ],
            "default_actions": [
                {
                    "type": AutomationActionType.send_notification,
                    "config": {
                        "to": "assigned_staff",
                        "message": "Engagement deadline in 14 days — check task count",
                    },
                    "order": 0,
                },
            ],  # exact copy of actions above
            "execution_count": 0,
            "last_executed_at": None,
            "created_at": now,
            "updated_at": now,
        },
        # PRESET 14 — Return Completed: Client Delivery Loop
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "Return Completed: Client Delivery Loop",
            "description": (
                "Creates delivery task, generates invoice, and notifies client "
                "when a return is complete."
            ),
            "is_enabled": False,
            "trigger_event": TriggerEvent.engagement_completed,
            "trigger_conditions": [],
            "actions": [
                {
                    "type": AutomationActionType.create_task,
                    "config": {"title": "Upload final return to client portal"},
                    "order": 0,
                },
                {
                    "type": AutomationActionType.create_invoice,
                    "config": {"source": "time_entries"},
                    "order": 1,
                },
                {
                    "type": AutomationActionType.send_email,
                    "config": {"template": "return_ready"},
                    "order": 2,
                },
                {
                    "type": AutomationActionType.create_task,
                    "config": {"title": "Confirm client acknowledgment within 5 days"},
                    "order": 3,
                },
            ],
            "default_actions": [
                {
                    "type": AutomationActionType.create_task,
                    "config": {"title": "Upload final return to client portal"},
                    "order": 0,
                },
                {
                    "type": AutomationActionType.create_invoice,
                    "config": {"source": "time_entries"},
                    "order": 1,
                },
                {
                    "type": AutomationActionType.send_email,
                    "config": {"template": "return_ready"},
                    "order": 2,
                },
                {
                    "type": AutomationActionType.create_task,
                    "config": {"title": "Confirm client acknowledgment within 5 days"},
                    "order": 3,
                },
            ],  # exact copy of actions above
            "execution_count": 0,
            "last_executed_at": None,
            "created_at": now,
            "updated_at": now,
        },
        # PRESET 15 — New Client Full Onboarding Sequence
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "New Client Full Onboarding Sequence",
            "description": (
                "Sends welcome email, creates onboarding tasks, and sends intake "
                "document request for new clients."
            ),
            "is_enabled": False,
            "trigger_event": TriggerEvent.client_created,
            "trigger_conditions": [],
            "actions": [
                {
                    "type": AutomationActionType.send_email,
                    "config": {"template": "client_portal_welcome"},
                    "order": 0,
                },
                {
                    "type": AutomationActionType.create_task,
                    "config": {"title": "Schedule onboarding call"},
                    "order": 1,
                },
                {
                    "type": AutomationActionType.create_task,
                    "config": {"title": "Collect entity documents"},
                    "order": 2,
                },
            ],
            "default_actions": [
                {
                    "type": AutomationActionType.send_email,
                    "config": {"template": "client_portal_welcome"},
                    "order": 0,
                },
                {
                    "type": AutomationActionType.create_task,
                    "config": {"title": "Schedule onboarding call"},
                    "order": 1,
                },
                {
                    "type": AutomationActionType.create_task,
                    "config": {"title": "Collect entity documents"},
                    "order": 2,
                },
            ],  # exact copy of actions above
            "execution_count": 0,
            "last_executed_at": None,
            "created_at": now,
            "updated_at": now,
        },
    ]


# TODO: call seed_firm_presets(firm_id, db) here when
# firm creation endpoint is built in a future phase
