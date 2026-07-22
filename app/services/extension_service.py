# app/services/extension_service.py

from uuid import UUID

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import TriggerEvent
from app.crud import extension as crud_extension
from app.models.engagement import Engagement
from app.services.audit_service import write_audit_log
from app.services.behavioral_log import log_event
from app.services.event_bus import emit_event


async def file_extension(
    *,
    db: Session,
    payload,  # ExtensionCreate
    engagement: Engagement,
    firm_id: UUID,
    actor_id: UUID,
    background_tasks: BackgroundTasks,
):
    """
    File an IRS extension for an engagement.

    Creates the Extension record, syncs Engagement.extended_deadline (the field
    the deadline scheduler and all deadline-watch queries use from this point
    forward), writes the audit log, emits the automation trigger event, and
    fires engagement.extension_filed.

    Caller (router) fetches/validates the engagement and raises HTTP errors
    before calling this.

    This mutates engagement.extended_deadline directly rather than going through
    engagement_service.update_engagement, so it does not also trigger that
    function's own (payload-driven) engagement.extension_filed branch.
    """
    original_deadline = engagement.filing_deadline

    extension = crud_extension.create_extension(
        db=db,
        ext_in=payload,
        firm_id=firm_id,
    )

    engagement.extended_deadline = extension.extended_deadline
    db.commit()
    db.refresh(engagement)

    write_audit_log(
        db=db,
        firm_id=firm_id,
        actor_id=actor_id,
        action="extension.filed",
        entity_type="extension",
        entity_id=extension.id,
    )

    await emit_event(
        event=TriggerEvent.extension_filed,
        payload={
            "firm_id": str(firm_id),
            "engagement_id": str(engagement.id),
            "client_id": str(engagement.client_id),
            "extension_id": str(extension.id),
            "form_type": extension.form_type,
            "extended_deadline": extension.extended_deadline.isoformat(),
        },
        background_tasks=background_tasks,
    )

    log_event(
        firm_id=firm_id,
        event_type="engagement.extension_filed",
        entity_type="engagement",
        entity_id=engagement.id,
        actor_type="staff",
        actor_id=actor_id,
        metadata={
            "extension_id": str(extension.id),
            "form_type": extension.form_type,
            "original_deadline": original_deadline.isoformat() if original_deadline else None,
            "new_extended_deadline": extension.extended_deadline.isoformat(),
            "days_before_original_deadline": (
                (original_deadline - extension.filed_at).days
                if original_deadline else None
            ),
        }
    )

    return extension


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
