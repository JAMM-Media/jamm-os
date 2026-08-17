# app/crud/lead_activity.py

from datetime import datetime
from typing import NamedTuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.behavioral_event import BehavioralEvent
from app.models.lead_message import LeadMessage


class ActivityItem(NamedTuple):
    id: str
    type: str        # "message" | "event"
    occurred_at: datetime
    description: str
    source_type: str  # raw event_type or message source tag


_EVENT_LABELS: dict[str, str] = {
    "lead.created":       "Lead added",
    "lead.converted":     "Converted to client",
    "lead.lost":          "Marked as lost",
    "lead.reopened":      "Lead reopened",
    "lead.email_replied": "Email reply received",
    "lead.call_booked":   "Call booked",
    "lead.call_held":     "Call completed",
    "lead.call_no_show":  "Call: no show",
    "lead.unsubscribed":  "Lead unsubscribed",
}


def _event_label(event_type: str) -> str:
    if event_type in _EVENT_LABELS:
        return _EVENT_LABELS[event_type]
    slug = event_type.split(".")[-1] if "." in event_type else event_type
    return slug.replace("_", " ").capitalize()


def _message_label(sender_role: str, source: str | None) -> str:
    if sender_role == "lead":
        return "Message from lead"
    src = source or ""
    if src == "inbound_email":
        return "Inbound email"
    if src == "staff_note":
        return "Staff note"
    if src == "form_reply":
        return "Form reply"
    return "Outbound message"


def get_lead_activity(
    db: Session,
    lead_id: UUID,
    firm_id: UUID,
    limit: int = 50,
) -> list[ActivityItem]:
    """Return combined LeadMessage + BehavioralEvent rows for one lead,
    newest first, scoped to the given firm."""

    events = (
        db.query(BehavioralEvent)
        .filter(
            BehavioralEvent.firm_id == firm_id,
            BehavioralEvent.entity_type == "lead",
            BehavioralEvent.entity_id == lead_id,
        )
        .all()
    )

    messages = (
        db.query(LeadMessage)
        .filter(
            LeadMessage.firm_id == firm_id,
            LeadMessage.lead_id == lead_id,
            LeadMessage.is_deleted == False,  # noqa: E712
        )
        .all()
    )

    items: list[ActivityItem] = []

    for evt in events:
        items.append(ActivityItem(
            id=str(evt.event_id),
            type="event",
            occurred_at=evt.occurred_at,
            description=_event_label(evt.event_type),
            source_type=evt.event_type,
        ))

    for msg in messages:
        items.append(ActivityItem(
            id=str(msg.id),
            type="message",
            occurred_at=msg.created_at,
            description=_message_label(msg.sender_role, msg.source),
            source_type=msg.source or msg.sender_role,
        ))

    items.sort(key=lambda x: x.occurred_at, reverse=True)
    return items[:limit]
