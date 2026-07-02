# app/services/firm_service.py

from uuid import UUID

from sqlalchemy.orm import Session

from app.crud import firm as crud_firm
from app.schemas.firm import FirmCreate
from app.services.behavioral_log import log_event


def create_firm(
    db: Session,
    firm_in: FirmCreate,
    *,
    current_user_id: UUID,
):
    firm = crud_firm.create_firm(db, firm_in)

    log_event(
        firm_id=firm.id,
        event_type="firm.created",
        entity_type="firm",
        entity_id=firm.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "signup_source": firm.signup_source,
            "plan_tier": firm.subscription_tier,
        },
    )

    return firm
