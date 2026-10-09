# app/crud/calendar_event.py

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.calendar_event import CalendarEvent
from app.schemas.calendar_event import CalendarEventCreate


def _with_rels(stmt):
    return stmt.options(
        selectinload(CalendarEvent.category),
        selectinload(CalendarEvent.client),
        selectinload(CalendarEvent.owner),
    )


def get_event_for_firm(
    db: Session,
    event_id: UUID,
    firm_id: UUID,
    include_deleted: bool = False,
) -> CalendarEvent | None:
    stmt = _with_rels(
        select(CalendarEvent).where(
            CalendarEvent.id == event_id,
            CalendarEvent.firm_id == firm_id,
        )
    )
    if not include_deleted:
        stmt = stmt.where(CalendarEvent.deleted_at.is_(None))
    return db.execute(stmt).scalar_one_or_none()


def list_events(
    db: Session,
    firm_id: UUID,
    range_start: datetime,
    range_end: datetime,
    owner_user_id: Optional[UUID] = None,
    category_id: Optional[UUID] = None,
    include_deleted: bool = False,
    limit: int = 50,
    offset: int = 0,
    staff_scope_user_id: Optional[UUID] = None,
) -> tuple[list[CalendarEvent], int]:
    base = select(CalendarEvent).where(
        CalendarEvent.firm_id == firm_id,
        CalendarEvent.start_at < range_end,
        CalendarEvent.end_at > range_start,
    )
    if not include_deleted:
        base = base.where(CalendarEvent.deleted_at.is_(None))
    if owner_user_id:
        base = base.where(CalendarEvent.owner_user_id == owner_user_id)
    if category_id:
        base = base.where(CalendarEvent.category_id == category_id)
    if staff_scope_user_id is not None:
        base = base.where(
            or_(
                CalendarEvent.owner_user_id == staff_scope_user_id,
                CalendarEvent.owner_user_id.is_(None),
            )
        )

    count_stmt = select(func.count()).select_from(base.subquery())
    total = db.execute(count_stmt).scalar_one()

    stmt = _with_rels(base).order_by(
        CalendarEvent.start_at, CalendarEvent.id
    ).offset(offset).limit(limit)
    items = list(db.execute(stmt).scalars())
    return items, total


def create_event(
    db: Session,
    payload: CalendarEventCreate,
    firm_id: UUID,
    event_timezone: str,
    created_by: UUID,
) -> CalendarEvent:
    data = payload.model_dump()
    ev = CalendarEvent(
        firm_id=firm_id,
        event_timezone=event_timezone,
        created_by=created_by,
        **data,
    )
    db.add(ev)
    db.commit()
    ev_id = ev.id
    return get_event_for_firm(db, ev_id, firm_id, include_deleted=True)


def update_event(
    db: Session,
    ev: CalendarEvent,
    updates: dict,
) -> CalendarEvent:
    firm_id = ev.firm_id
    ev_id = ev.id
    for key, value in updates.items():
        setattr(ev, key, value)
    db.commit()
    return get_event_for_firm(db, ev_id, firm_id, include_deleted=True)


def soft_delete_event(db: Session, ev: CalendarEvent) -> CalendarEvent:
    ev.deleted_at = datetime.now(tz=timezone.utc)
    db.commit()
    db.refresh(ev)
    return ev


def restore_event(db: Session, ev: CalendarEvent) -> CalendarEvent:
    firm_id = ev.firm_id
    ev_id = ev.id
    ev.deleted_at = None
    db.commit()
    return get_event_for_firm(db, ev_id, firm_id, include_deleted=False)
