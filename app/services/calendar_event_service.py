# app/services/calendar_event_service.py

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import calendar_event as crud_event
from app.models.calendar_category import CalendarCategory
from app.models.calendar_event import CalendarEvent
from app.models.client import Client
from app.models.user import User
from app.schemas.calendar_event import CalendarEventCreate, CalendarEventUpdate
from app.services.behavioral_log import log_event


def _validate_timezone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"'{tz_name}' is not a valid IANA timezone name.",
        )


def _validate_times(start_at: datetime, end_at: datetime, tz: ZoneInfo) -> None:
    if end_at <= start_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_at must be after start_at.",
        )
    if start_at.astimezone(tz).date() != end_at.astimezone(tz).date():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_at and end_at must fall on the same calendar date in the event timezone.",
        )


def _resolve_category(
    db: Session, category_id: UUID, firm_id: UUID, require_active: bool = True
) -> CalendarCategory:
    cat = db.execute(
        select(CalendarCategory).where(
            CalendarCategory.id == category_id,
            CalendarCategory.firm_id == firm_id,
        )
    ).scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")
    if require_active and not cat.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot assign an inactive category.",
        )
    return cat


def _resolve_client(db: Session, client_id: UUID, firm_id: UUID) -> Client:
    c = db.execute(
        select(Client).where(Client.id == client_id, Client.firm_id == firm_id)
    ).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found.")
    return c


def _resolve_owner(db: Session, owner_user_id: UUID, firm_id: UUID) -> User:
    u = db.execute(
        select(User).where(User.id == owner_user_id, User.firm_id == firm_id)
    ).scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if not u.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot assign an inactive user as owner.",
        )
    return u


def list_events(
    db: Session,
    firm_id: UUID,
    range_start: datetime,
    range_end: datetime,
    owner_user_id: Optional[UUID],
    category_id: Optional[UUID],
    include_deleted: bool,
    current_user,
    limit: int,
    offset: int,
) -> dict:
    items, total = crud_event.list_events(
        db, firm_id, range_start, range_end,
        owner_user_id, category_id, include_deleted, limit, offset,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_event(db: Session, firm_id: UUID, event_id: UUID) -> CalendarEvent:
    ev = crud_event.get_event_for_firm(db, event_id, firm_id, include_deleted=False)
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")
    return ev


def create_event(
    db: Session,
    payload: CalendarEventCreate,
    firm_id: UUID,
    current_user_id: UUID,
    firm_timezone: str,
) -> CalendarEvent:
    tz = _validate_timezone(firm_timezone)
    _validate_times(payload.start_at, payload.end_at, tz)
    if payload.category_id:
        _resolve_category(db, payload.category_id, firm_id, require_active=True)
    if payload.client_id:
        _resolve_client(db, payload.client_id, firm_id)
    if payload.owner_user_id:
        _resolve_owner(db, payload.owner_user_id, firm_id)
    ev = crud_event.create_event(
        db, payload, firm_id=firm_id, event_timezone=firm_timezone, created_by=current_user_id
    )
    duration_minutes = int((ev.end_at - ev.start_at).total_seconds() / 60)
    log_event(
        firm_id=firm_id,
        event_type="calendar_event.created",
        entity_type="calendar_event",
        entity_id=ev.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "duration_minutes": duration_minutes,
            "has_category": ev.category_id is not None,
            "has_client": ev.client_id is not None,
            "has_owner": ev.owner_user_id is not None,
        },
    )
    return ev


def update_event(
    db: Session,
    event_id: UUID,
    payload: CalendarEventUpdate,
    firm_id: UUID,
    current_user_id: UUID,
) -> CalendarEvent:
    ev = crud_event.get_event_for_firm(db, event_id, firm_id, include_deleted=False)
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")
    updates = payload.model_dump(exclude_unset=True)
    real_changes = {k: v for k, v in updates.items() if getattr(ev, k) != v}
    if not real_changes:
        return ev
    times_changed = "start_at" in real_changes or "end_at" in real_changes
    if times_changed:
        new_start = real_changes.get("start_at", ev.start_at)
        new_end = real_changes.get("end_at", ev.end_at)
        tz = _validate_timezone(ev.event_timezone)
        _validate_times(new_start, new_end, tz)
    if "category_id" in real_changes and real_changes["category_id"] is not None:
        _resolve_category(db, real_changes["category_id"], firm_id, require_active=True)
    if "client_id" in real_changes and real_changes["client_id"] is not None:
        _resolve_client(db, real_changes["client_id"], firm_id)
    if "owner_user_id" in real_changes and real_changes["owner_user_id"] is not None:
        _resolve_owner(db, real_changes["owner_user_id"], firm_id)
    old_start = ev.start_at
    old_end = ev.end_at
    ev = crud_event.update_event(db, ev, real_changes)
    if times_changed:
        log_event(
            firm_id=firm_id,
            event_type="calendar_event.moved",
            entity_type="calendar_event",
            entity_id=ev.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "old_start_at": old_start.isoformat(),
                "old_end_at": old_end.isoformat(),
                "new_start_at": ev.start_at.isoformat(),
                "new_end_at": ev.end_at.isoformat(),
            },
        )
        other_fields = [f for f in real_changes if f not in ("start_at", "end_at")]
        if other_fields:
            log_event(
                firm_id=firm_id,
                event_type="calendar_event.updated",
                entity_type="calendar_event",
                entity_id=ev.id,
                actor_type="staff",
                actor_id=current_user_id,
                metadata={"changed_fields": other_fields},
            )
    else:
        log_event(
            firm_id=firm_id,
            event_type="calendar_event.updated",
            entity_type="calendar_event",
            entity_id=ev.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={"changed_fields": list(real_changes.keys())},
        )
    return ev


def delete_event(
    db: Session,
    event_id: UUID,
    firm_id: UUID,
    current_user_id: UUID,
) -> None:
    ev = crud_event.get_event_for_firm(db, event_id, firm_id, include_deleted=False)
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")
    crud_event.soft_delete_event(db, ev)
    log_event(
        firm_id=firm_id,
        event_type="calendar_event.deleted",
        entity_type="calendar_event",
        entity_id=event_id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={},
    )


def restore_event(
    db: Session,
    event_id: UUID,
    firm_id: UUID,
    current_user_id: UUID,
) -> CalendarEvent:
    ev = crud_event.get_event_for_firm(db, event_id, firm_id, include_deleted=True)
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")
    if ev.deleted_at is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Event is not deleted.")
    ev = crud_event.restore_event(db, ev)
    log_event(
        firm_id=firm_id,
        event_type="calendar_event.restored",
        entity_type="calendar_event",
        entity_id=event_id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={},
    )
    return ev
