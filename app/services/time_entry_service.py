# app/services/time_entry_service.py

from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.core.enums import UserRole

from app.crud import time_entry as crud_time_entry
from app.models.engagement import Engagement
from app.models.user import User
from app.services.behavioral_log import log_event


def create_time_entry(
    *,
    db: Session,
    payload,  # TimeEntryCreate
    firm_id: UUID,
    current_user: User,
):
    engagement = db.execute(
        select(Engagement).where(
            Engagement.id == payload.engagement_id,
            Engagement.firm_id == firm_id,
        )
    ).scalar_one_or_none()
    if not engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")

    entry = crud_time_entry.create_time_entry(
        db,
        entry_in=payload,
        firm_id=firm_id,
        user_id=current_user.id,
    )

    log_event(
        firm_id=firm_id,
        event_type="time_entry.created",
        entity_type="time_entry",
        entity_id=entry.id,
        actor_type="staff",
        actor_id=current_user.id,
        metadata={
            "hours": float(entry.hours) if entry.hours else None,
            "billable": entry.is_billable if hasattr(entry, 'is_billable') else None,
            "engagement_id": str(entry.engagement_id) if entry.engagement_id else None,
            "engagement_type": str(engagement.engagement_type)
                if engagement.engagement_type else None,
        }
    )

    return entry


def update_time_entry(
    *,
    db: Session,
    entry_id: UUID,
    payload,  # TimeEntryUpdate
    firm_id: UUID,
    current_user: User,
):
    entry = crud_time_entry.get_time_entry(db, entry_id, firm_id=firm_id)
    if not entry:
        return None, "not_found"
    if current_user.role == UserRole.staff and entry.user_id != current_user.id:
        return None, "access_denied"
    if entry.is_billed:
        return None, "billed"

    updated = crud_time_entry.update_time_entry(db, entry, payload)
    return updated, None


def delete_time_entry(
    *,
    db: Session,
    entry_id: UUID,
    firm_id: UUID,
    current_user: User,
):
    entry = crud_time_entry.get_time_entry(db, entry_id, firm_id=firm_id)
    if not entry:
        return None, "not_found"
    if entry.is_billed:
        return None, "billed"

    hours = float(entry.hours) if entry.hours else None
    entry_firm_id = entry.firm_id

    crud_time_entry.delete_time_entry(db, entry)

    log_event(
        firm_id=entry_firm_id,
        event_type="time_entry.deleted",
        entity_type="time_entry",
        entity_id=entry_id,
        actor_type="staff",
        actor_id=current_user.id,
        metadata={
            "hours": hours,
        }
    )

    return True, None
