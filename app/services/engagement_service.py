# app/services/engagement_service.py

from datetime import datetime, timedelta, timezone
from uuid import UUID
from typing import Optional
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.crud import engagement as crud_engagement
from app.crud.qc_checklist import populate_from_template
from app.models.client import Client as ClientModel
from app.models.engagement import Engagement
from app.models.invoice import Invoice
from app.models.task import Task
from app.models.document import Document
from app.models.time_entry import TimeEntry
from app.schemas.engagement import EngagementCreate
from app.core.enums import TriggerEvent
from app.services.audit_service import write_audit_log
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

    # The creator becomes an administrator of the engagement they just made.
    # Imported inside the function: engagement_member_service imports nothing
    # from here today, but keeping the dependency one-directional at module
    # scope removes the possibility of a cycle as either side grows.
    from app.services import engagement_member_service

    engagement_member_service.ensure_creator_is_administrator(
        db=db,
        firm_id=firm_id,
        engagement_id=engagement.id,
        current_user_id=current_user_id,
    )

    if engagement.engagement_type:
        populate_from_template(
            db=db,
            firm_id=firm_id,
            engagement_id=engagement.id,
            engagement_type=engagement.engagement_type,
        )

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

    if engagement.filing_deadline:
        log_event(
            firm_id=engagement.firm_id,
            event_type="engagement.deadline_set",
            entity_type="engagement",
            entity_id=engagement.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "deadline_type": "filing_deadline",
                "deadline_date": engagement.filing_deadline.isoformat(),
                "days_until_deadline": (engagement.filing_deadline - datetime.now(timezone.utc).date()).days,
                "form_type": str(engagement.engagement_type) if engagement.engagement_type else None,
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

    # Fields already covered by a dedicated event below -- excluded from the
    # generic no-silent-changes delta so they are not double-logged.
    _EVENTED_FIELDS = {"status", "filing_deadline", "extended_deadline"}
    _tracked_fields = [
        f for f in payload.model_dump(exclude_unset=True).keys()
        if f not in _EVENTED_FIELDS
    ]
    _old_values = {f: getattr(engagement, f) for f in _tracked_fields}

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

        if old_status == "completed" and new_status not in ("archived", "completed"):
            log_event(
                firm_id=updated.firm_id,
                event_type="engagement.reopened",
                entity_type="engagement",
                entity_id=updated.id,
                actor_type="staff",
                actor_id=current_user_id,
                metadata={
                    "reopened_to_status": new_status,
                    "form_type": str(updated.engagement_type) if updated.engagement_type else None,
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

    from app.services.behavioral_log import build_changed_fields

    _new_values = {f: getattr(updated, f) for f in _tracked_fields}
    _changed_fields = build_changed_fields(_old_values, _new_values)
    if _changed_fields:
        log_event(
            firm_id=updated.firm_id,
            event_type="engagement.updated",
            entity_type="engagement",
            entity_id=updated.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={"changed_fields": _changed_fields},
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

    # This is a hard delete. Documents cascade away with the engagement and
    # time entries cannot survive it at all (their engagement_id is NOT NULL),
    # so anything still attached has to be dealt with before the row goes.
    document_count = db.execute(
        select(func.count()).select_from(Document).where(
            Document.engagement_id == engagement_id,
            Document.firm_id == firm_id,
        )
    ).scalar()
    time_entry_count = db.execute(
        select(func.count()).select_from(TimeEntry).where(
            TimeEntry.engagement_id == engagement_id,
            TimeEntry.firm_id == firm_id,
        )
    ).scalar()
    # Soft-deleted invoices are excluded: they are already gone everywhere else
    # in the app, so blocking on one would refuse a deletion for a row the user
    # has no way to see or clear.
    invoice_count = db.execute(
        select(func.count()).select_from(Invoice).where(
            Invoice.engagement_id == engagement_id,
            Invoice.firm_id == firm_id,
            Invoice.is_deleted == False,  # noqa: E712
        )
    ).scalar()

    attached = []
    if document_count:
        attached.append(f"{document_count} document{'s' if document_count != 1 else ''}")
    if time_entry_count:
        attached.append(f"{time_entry_count} time entr{'ies' if time_entry_count != 1 else 'y'}")
    if invoice_count:
        attached.append(f"{invoice_count} invoice{'s' if invoice_count != 1 else ''}")

    if attached:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot delete engagement: {', '.join(attached)} attached. "
                "Remove or reassign them first."
            ),
        )

    days_active = (datetime.now(timezone.utc) - engagement.created_at).days \
        if engagement.created_at else None
    completion_status = str(engagement.status) if engagement.status else None
    form_type = str(engagement.engagement_type) if engagement.engagement_type else None
    eng_firm_id = engagement.firm_id

    crud_engagement.delete_engagement(db, engagement)

    log_event(
        firm_id=eng_firm_id,
        event_type="engagement.deleted",
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


def bulk_update_engagements(
    *,
    db: Session,
    ids,
    update,  # BulkEngagementFieldUpdate
    firm_id: UUID,
):
    stmt = select(Engagement).where(
        Engagement.id.in_(ids),
        Engagement.firm_id == firm_id,
    )
    engagements = db.execute(stmt).scalars().all()
    changed = []
    for eng in engagements:
        old_status = eng.status
        old_filing = eng.filing_deadline
        old_extended = eng.extended_deadline
        if update.status is not None:
            eng.status = update.status
        if update.deadline_push_days is not None:
            delta = timedelta(days=update.deadline_push_days)
            if eng.extended_deadline is not None:
                eng.extended_deadline = eng.extended_deadline + delta
            elif eng.filing_deadline is not None:
                eng.filing_deadline = eng.filing_deadline + delta
        changed.append((eng, old_status, old_filing, old_extended))
    db.commit()

    for eng, old_status, old_filing, old_extended in changed:
        if update.status is not None and eng.status != old_status:
            log_event(
                firm_id=firm_id,
                event_type="engagement.status_changed",
                entity_type="engagement",
                entity_id=eng.id,
                actor_type="staff",
                actor_id=None,
                metadata={
                    "from_status": str(old_status),
                    "to_status": str(eng.status),
                    "via": "bulk",
                }
            )
        if eng.filing_deadline != old_filing or eng.extended_deadline != old_extended:
            log_event(
                firm_id=firm_id,
                event_type="engagement.deadline_changed",
                entity_type="engagement",
                entity_id=eng.id,
                actor_type="staff",
                actor_id=None,
                metadata={
                    "from_filing_deadline": old_filing.isoformat() if old_filing else None,
                    "to_filing_deadline": eng.filing_deadline.isoformat() if eng.filing_deadline else None,
                    "from_extended_deadline": old_extended.isoformat() if old_extended else None,
                    "to_extended_deadline": eng.extended_deadline.isoformat() if eng.extended_deadline else None,
                    "via": "bulk",
                    "push_days": update.deadline_push_days,
                }
            )

    return {"updated": len(engagements)}


def bulk_create_engagements(
    *,
    db: Session,
    payload,  # BulkEngagementCreate
    firm_id: UUID,
    current_user_id: UUID,
):
    created_ids = []
    skipped = 0

    for client_id in payload.client_ids:
        client = db.execute(
            select(ClientModel).where(
                ClientModel.id == client_id,
                ClientModel.firm_id == firm_id,
            )
        ).scalars().first()
        if not client:
            skipped += 1
            continue

        eng_create = EngagementCreate(
            client_id=client.id,
            name=payload.name,
            engagement_type=payload.engagement_type,
            status=payload.status,
            start_date=payload.start_date,
            end_date=payload.end_date,
            notes=payload.notes,
            filing_deadline=payload.filing_deadline,
        )
        engagement = crud_engagement.create_engagement(db, eng_create, firm_id=firm_id)

        from app.services import engagement_member_service

        engagement_member_service.ensure_creator_is_administrator(
            db=db,
            firm_id=firm_id,
            engagement_id=engagement.id,
            current_user_id=current_user_id,
        )

        write_audit_log(
            db=db,
            firm_id=firm_id,
            action="engagement.bulk_created",
            actor_id=current_user_id,
            actor_type="staff",
            entity_type="engagement",
            entity_id=engagement.id,
        )

        log_event(
            firm_id=firm_id,
            event_type="engagement.created",
            entity_type="engagement",
            entity_id=engagement.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "form_type": str(engagement.engagement_type) if engagement.engagement_type else None,
                "client_id": str(engagement.client_id),
                "filing_deadline": engagement.filing_deadline.isoformat() if engagement.filing_deadline else None,
                "via": "bulk_create",
            }
        )
        if engagement.filing_deadline:
            log_event(
                firm_id=firm_id,
                event_type="engagement.deadline_set",
                entity_type="engagement",
                entity_id=engagement.id,
                actor_type="staff",
                actor_id=current_user_id,
                metadata={
                    "deadline_type": "filing_deadline",
                    "deadline_date": engagement.filing_deadline.isoformat(),
                    "via": "bulk_create",
                    "engagement_type": str(engagement.engagement_type) if engagement.engagement_type else None,
                }
            )

        created_ids.append(engagement.id)

    return created_ids, skipped


def update_complexity_flags(
    *,
    db: Session,
    engagement_id: UUID,
    firm_id: UUID,
    flags: dict,
    current_user_id: UUID,
):
    engagement = crud_engagement.get_engagement_for_firm(db, engagement_id, firm_id)
    if not engagement:
        return None

    old_flags = engagement.complexity_flags

    engagement.complexity_flags = flags
    db.commit()
    db.refresh(engagement)

    log_event(
        firm_id=firm_id,
        event_type="engagement.complexity_flags_updated",
        entity_type="engagement",
        entity_id=engagement.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "engagement_id": str(engagement.id),
            "engagement_type": engagement.engagement_type,
            "flags": flags,
            "actor_id": str(current_user_id),
            "from_flags": old_flags,
            "to_flags": flags,
        },
    )

    return engagement
