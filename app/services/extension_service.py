# app/services/extension_service.py

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import extension as crud_extension
from app.models.engagement import Engagement
from app.services.behavioral_log import log_event


def update_extension(
    *,
    db: Session,
    ext,
    payload,  # ExtensionUpdate
    firm_id,
):
    updated = crud_extension.update_extension(db, ext, payload)

    # If the deadline was updated, sync it to the engagement
    if payload.extended_deadline is not None:
        engagement = db.execute(
            select(Engagement).where(
                Engagement.id == ext.engagement_id,
                Engagement.firm_id == firm_id,
            )
        ).scalars().first()
        if engagement:
            old_extended = engagement.extended_deadline
            engagement.extended_deadline = payload.extended_deadline
            db.commit()

            if engagement.extended_deadline != old_extended:
                log_event(
                    firm_id=firm_id,
                    event_type="engagement.deadline_changed",
                    entity_type="engagement",
                    entity_id=engagement.id,
                    actor_type="staff",
                    actor_id=None,
                    metadata={
                        "from_extended_deadline": old_extended.isoformat() if old_extended else None,
                        "to_extended_deadline": engagement.extended_deadline.isoformat() if engagement.extended_deadline else None,
                        "via": "extension_update",
                        "extension_id": str(ext.id),
                    }
                )

    return updated
