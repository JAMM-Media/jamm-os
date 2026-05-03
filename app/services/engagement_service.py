# app/services/engagement_service.py

from datetime import datetime, timezone
from uuid import UUID
from typing import Optional
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.crud import engagement as crud_engagement
from app.models.engagement import Engagement
from app.models.task import Task
from app.models.document import Document
from app.models.time_entry import TimeEntry
from app.core.enums import TriggerEvent
from app.services.event_bus import emit_event
from app.services.behavioral_log import log_event


async def create_engagement(
    *,
    db: Session,
    payload,
    firm_id: UUID,
    current_user_id: UUID,
    background_tasks: BackgroundTasks,
):
    engagement = crud_engagement.create_engagement(db, payload, firm_id=firm_id)

    await emit_event(
        event=TriggerEvent.engagement_created,
        payload={
            "firm_id": str(engagement.firm_id),
            "engagement_id": str(engagement.id),
            "client_id": str(engagement.client_id),
            "engagement_type": str(engagement.engagement_type) if engagement.engagement_type else None,
            "status": str(engagement.status),
        },
        background_tasks=background_tasks,
    )

    engagement_count = db.execute(
        select(func.count()).where(Engagement.firm_id == firm_id)
    ).scalar()

    log_event(
        firm_id=engagement.firm_id,
        event_type="engagement.created",
        entity_type="engagement",
        entity_id=engagement.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "form_type": str(engagement.engagement_type) if engagement.engagement_type else None,
            "client_id": str(engagement.client_id),
            "assigned_staff_id": str(engagement.assigned_to) if hasattr(engagement, 'assigned_to') and engagement.assigned_to else None,
            "filing_deadline": engagement.filing_deadline.isoformat() if engagement.filing_deadline else None,
            "days_until_deadline": (engagement.filing_deadline - datetime.now(timezone.utc).date()).days
                if engagement.filing_deadline else None,
        }
    )

    if engagement_count == 1:
        log_event(
            firm_id=engagement.firm_id,
            event_type="firm.first_engagement_created",
            entity_type="firm",
            entity_id=engagement.firm_id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={}
        )

    return engagement


async def update_engagement(
    *,
    db: Session,
    engagement_id: UUID,
    payload,
    firm_id: UUID,
    current_user_id: UUID,
    background_tasks: BackgroundTasks,
):
    engagement = crud_engagement.get_engagement_for_firm(db, engagement_id, firm_id)
    if not engagement:
        return None

    old_status = str(engagement.status) if engagement.status else None
    old_deadline = engagement.filing_deadline
    old_assigned = str(engagement.assigned_to) if hasattr(engagement, 'assigned_to') and engagement.assigned_to else None

    updated = crud_engagement.update_engagement(db, engagement, payload)

    new_status = str(updated.status) if updated.status else None

    if payload.status is not None and payload.status != old_status:
        event_payload = {
            "firm_id": str(updated.firm_id),
            "engagement_id": str(updated.id),
            "client_id": str(updated.client_id),
            "old_status": old_status,
            "new_status": payload.status,
        }
        await emit_event(
            event=TriggerEvent.engagement_status_changed,
            payload=event_payload,
            background_tasks=background_tasks,
        )
        if payload.status == "completed":
            await emit_event(
                event=TriggerEvent.engagement_completed,
                payload=event_payload,
                background_tasks=background_tasks,
            )

    if old_status != new_status:
        log_event(
            firm_id=updated.firm_id,
            event_type="engagement.status_changed",
            entity_type="engagement",
            entity_id=updated.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "from_status": old_status,
                "to_status": new_status,
                "days_since_creation": (datetime.now(timezone.utc) - updated.created_at).days
                    if updated.created_at else None,
            }
        )

        if new_status == "completed":
            try:
                task_count = db.execute(
                    select(func.count()).where(Task.engagement_id == updated.id)
                ).scalar()
            except Exception:
                task_count = None
            try:
                doc_count = db.execute(
                    select(func.count()).where(Document.engagement_id == updated.id)
                ).scalar()
            except Exception:
                doc_count = None

            log_event(
                firm_id=updated.firm_id,
                event_type="engagement.completed",
                entity_type="engagement",
                entity_id=updated.id,
                actor_type="staff",
                actor_id=current_user_id,
                metadata={
                    "form_type": str(updated.engagement_type) if updated.engagement_type else None,
                    "total_days": (datetime.now(timezone.utc) - updated.created_at).days
                        if updated.created_at else None,
                    "total_tasks": task_count,
                    "total_documents": doc_count,
                    "filing_deadline": updated.filing_deadline.isoformat()
                        if updated.filing_deadline else None,
                    "extended_deadline": updated.extended_deadline.isoformat()
                        if hasattr(updated, 'extended_deadline') and updated.extended_deadline else None,
                }
            )

    new_assigned = str(updated.assigned_to) if hasattr(updated, 'assigned_to') and updated.assigned_to else None
    if old_assigned != new_assigned and payload.model_dump(exclude_none=True).get('assigned_to') is not None:
        log_event(
            firm_id=updated.firm_id,
            event_type="engagement.assigned",
            entity_type="engagement",
            entity_id=updated.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "from_staff_id": old_assigned,
                "to_staff_id": new_assigned,
            }
        )

    if old_deadline != updated.filing_deadline and payload.model_dump(exclude_none=True).get('filing_deadline') is not None:
        log_event(
            firm_id=updated.firm_id,
            event_type="engagement.deadline_changed",
            entity_type="engagement",
            entity_id=updated.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "old_deadline": old_deadline.isoformat() if old_deadline else None,
                "new_deadline": updated.filing_deadline.isoformat() if updated.filing_deadline else None,
                "deadline_type": "filing_deadline",
            }
        )

    if hasattr(payload, 'extended_deadline') and payload.extended_deadline is not None:
        log_event(
            firm_id=updated.firm_id,
            event_type="engagement.extension_filed",
            entity_type="engagement",
            entity_id=updated.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "original_deadline": updated.filing_deadline.isoformat()
                    if updated.filing_deadline else None,
                "new_extended_deadline": updated.extended_deadline.isoformat()
                    if hasattr(updated, 'extended_deadline') and updated.extended_deadline else None,
                "form_type": str(updated.engagement_type) if updated.engagement_type else None,
            }
        )

    return updated


def delete_engagement(
    *,
    db: Session,
    engagement_id: UUID,
    firm_id: UUID,
    current_user_id: UUID,
):
    engagement = crud_engagement.get_engagement_for_firm(db, engagement_id, firm_id)
    if not engagement:
        return None

    days_active = (datetime.now(timezone.utc) - engagement.created_at).days \
        if engagement.created_at else None
    completion_status = str(engagement.status) if engagement.status else None
    form_type = str(engagement.engagement_type) if engagement.engagement_type else None
    eng_firm_id = engagement.firm_id

    crud_engagement.delete_engagement(db, engagement)

    log_event(
        firm_id=eng_firm_id,
        event_type="engagement.archived",
        entity_type="engagement",
        entity_id=engagement_id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "days_active": days_active,
            "completion_status": completion_status,
            "form_type": form_type,
        }
    )

    return True
