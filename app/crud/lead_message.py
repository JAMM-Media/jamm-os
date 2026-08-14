# app/crud/lead_message.py

from uuid import UUID
from sqlalchemy.orm import Session

from app.models.lead_message import LeadMessage


def get_messages_for_lead(
    db: Session, lead_id: UUID, firm_id: UUID
) -> list[LeadMessage]:
    return (
        db.query(LeadMessage)
        .filter(
            LeadMessage.lead_id == lead_id,
            LeadMessage.firm_id == firm_id,
        )
        .order_by(LeadMessage.created_at)
        .all()
    )


def create_lead_message(
    db: Session,
    firm_id: UUID,
    lead_id: UUID,
    body: str,
    source: str | None = None,
) -> LeadMessage:
    """Record a sent nurture email as a LeadMessage row."""
    msg = LeadMessage(
        firm_id=firm_id,
        lead_id=lead_id,
        sender_id=None,
        sender_role="staff",
        body=body,
        source=source,
        is_deleted=False,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg
