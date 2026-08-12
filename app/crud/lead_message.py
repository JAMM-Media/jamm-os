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
