# app/services/calendar_event_service.py

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import UserRole
from app.crud import calendar_event as crud_event
from app.models.calendar_category import CalendarCategory
from app.models.calendar_event import CalendarEvent
from app.models.client import Client
from app.models.user import User
from app.schemas.calendar_event import CalendarEventCreate, CalendarEventUpdate
from app.services.behavioral_log import log_event


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

def _is_manager_or_above(user: User) -> bool:
    """Returns True when the user role grants full firm-wide calendar access."""
    return user.role in (UserRole.firm_owner, UserRole.manager, UserRole.system_admin)


def _can_view(user: User, ev: CalendarEvent) -> bool:
    """Returns True when the user is allowed to see this event."""
    if _is_manager_or_above(user):
        return True
    return ev.owner_user_id is None or ev.owner_user_id == user.id


def _can_edit_or_delete(user: User, ev: CalendarEvent) -> bool:
    """Returns True when the user created and owns the event (full edit rights)."""
    if _is_manager_or_above(user):
        return True
    if ev.created_by is None:
        return False
    return ev.created_by == user.id and ev.owner_user_id == user.id


def _can_annotate_only(user: User, ev: CalendarEvent) -> bool:
    """Returns True when staff own the event but did not create it (notes and done only)."""
    if _is_manager_or_above(user):
        return False
    return ev.owner_user_id == user.id and ev.created_by != user.id


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

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
    if u.role == UserRole.client_portal_user:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot assign a client portal user as owner.",
        )
    if not u.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot assign an inactive user as owner.",
        )
    return u


# ---------------------------------------------------------------------------
# Notification helper
# ---------------------------------------------------------------------------

def _notify_delete_request(db: Session, firm_id: UUID, ev: CalendarEvent, requester: User) -> None:
    """Send a quiet notification when a delete request is filed. Never raises."""
    try:
        from app.db.session import SessionLocal
        from app.services.notification_service import NotificationService
        from app.core.enums import NotificationType, NotificationTier, RecipientType

        requester_name = requester.full_name or requester.email
        body = f'{requester_name} has requested to delete "{ev.title}".'
        if ev.delete_request_reason:
            body += f' {ev.delete_request_reason}'
        notif_title = 'Delete request'

        recipient_ids: list = []
        if ev.created_by is not None:
            creator = db.execute(
                select(User).where(User.id == ev.created_by, User.firm_id == firm_id)
            ).scalar_one_or_none()
            if creator and creator.is_active and _is_manager_or_above(creator):
                recipient_ids = [creator.id]

        if not recipient_ids:
            managers = db.execute(
                select(User).where(
                    User.firm_id == firm_id,
                    User.role.in_([UserRole.firm_owner, UserRole.manager]),
                    User.is_active.is_(True),
                )
            ).scalars().all()
            recipient_ids = [u.id for u in managers]

        if not recipient_ids:
            return

        notification_db = SessionLocal()
        try:
            for recipient_id in recipient_ids:
                NotificationService.create_notification(
                    db=notification_db,
                    firm_id=firm_id,
                    recipient_id=recipient_id,
                    recipient_type=RecipientType.staff,
                    title=notif_title,
                    body=body,
                    notification_type=NotificationType.system,
                    tier=NotificationTier.quiet,
                    related_entity_type='calendar_event',
                    related_entity_id=ev.id,
                )
        finally:
            notification_db.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------

def list_events(
    db: Session,
    firm_id: UUID,
    range_start: datetime,
    range_end: datetime,
    owner_user_id: Optional[UUID],
    category_id: Optional[UUID],
    include_deleted: bool,
    current_user: User,
    limit: int,
    offset: int,
) -> dict:
    staff_scope = None
    if not _is_manager_or_above(current_user):
        if owner_user_id is not None and owner_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Staff can only filter by their own user id.",
            )
        staff_scope = current_user.id

    items, total = crud_event.list_events(
        db, firm_id, range_start, range_end,
        owner_user_id, category_id, include_deleted, limit, offset,
        staff_scope_user_id=staff_scope,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_event(db: Session, firm_id: UUID, event_id: UUID, current_user: User) -> CalendarEvent:
    ev = crud_event.get_event_for_firm(db, event_id, firm_id, include_deleted=False)
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")
    if not _can_view(current_user, ev):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")
    return ev


def create_event(
    db: Session,
    payload: CalendarEventCreate,
    firm_id: UUID,
    current_user: User,
    firm_timezone: str,
) -> CalendarEvent:
    tz = _validate_timezone(firm_timezone)
    _validate_times(payload.start_at, payload.end_at, tz)

    if not _is_manager_or_above(current_user):
        if payload.client_id is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Staff cannot assign a client to a calendar event.",
            )
        if payload.owner_user_id is not None and payload.owner_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Staff can only create events for themselves.",
            )
        payload = payload.model_copy(update={"owner_user_id": current_user.id})

    if payload.category_id:
        _resolve_category(db, payload.category_id, firm_id, require_active=True)
    if payload.client_id:
        _resolve_client(db, payload.client_id, firm_id)
    if payload.owner_user_id:
        _resolve_owner(db, payload.owner_user_id, firm_id)

    ev = crud_event.create_event(
        db, payload, firm_id=firm_id, event_timezone=firm_timezone, created_by=current_user.id
    )
    duration_minutes = int((ev.end_at - ev.start_at).total_seconds() / 60)
    log_event(
        firm_id=firm_id,
        event_type="calendar_event.created",
        entity_type="calendar_event",
        entity_id=ev.id,
        actor_type="staff",
        actor_id=current_user.id,
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
    current_user: User,
) -> CalendarEvent:
    ev = crud_event.get_event_for_firm(db, event_id, firm_id, include_deleted=False)
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")

    if not _can_view(current_user, ev):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")

    updates = payload.model_dump(exclude_unset=True)

    # Translate is_done to completed_at before building real_changes
    if "is_done" in updates:
        is_done_val = updates.pop("is_done")
        if is_done_val is True:
            if ev.completed_at is None:
                updates["completed_at"] = datetime.now(timezone.utc)
        elif is_done_val is False:
            updates["completed_at"] = None

    real_changes = {k: v for k, v in updates.items() if getattr(ev, k, None) != v}
    if not real_changes:
        return ev

    if not _can_edit_or_delete(current_user, ev):
        if not _can_annotate_only(current_user, ev):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to edit this event.",
            )
        # Annotation only: staff_notes and completed_at are the only allowed changes
        forbidden = {k for k in real_changes if k not in ("staff_notes", "completed_at")}
        if forbidden:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to edit this event.",
            )

    if not _is_manager_or_above(current_user):
        if "owner_user_id" in real_changes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Staff cannot change the owner of an event.",
            )
        if "client_id" in real_changes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Staff cannot change the client on an event.",
            )

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
            actor_id=current_user.id,
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
                actor_id=current_user.id,
                metadata={"changed_fields": other_fields},
            )
    else:
        log_event(
            firm_id=firm_id,
            event_type="calendar_event.updated",
            entity_type="calendar_event",
            entity_id=ev.id,
            actor_type="staff",
            actor_id=current_user.id,
            metadata={"changed_fields": list(real_changes.keys())},
        )
    return ev


def delete_event(
    db: Session,
    event_id: UUID,
    firm_id: UUID,
    current_user: User,
) -> None:
    ev = crud_event.get_event_for_firm(db, event_id, firm_id, include_deleted=False)
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")

    if not _can_view(current_user, ev):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")

    if not _can_edit_or_delete(current_user, ev):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this event.",
        )

    crud_event.soft_delete_event(db, ev)
    log_event(
        firm_id=firm_id,
        event_type="calendar_event.deleted",
        entity_type="calendar_event",
        entity_id=event_id,
        actor_type="staff",
        actor_id=current_user.id,
        metadata={},
    )


def restore_event(
    db: Session,
    event_id: UUID,
    firm_id: UUID,
    current_user: User,
) -> CalendarEvent:
    ev = crud_event.get_event_for_firm(db, event_id, firm_id, include_deleted=True)
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")
    if ev.deleted_at is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Event is not deleted.")
    ev = crud_event.restore_event(db, ev)
    # Per Decision 2: restore also clears any pending delete request
    ev = crud_event.update_event(db, ev, {
        "delete_requested_at": None,
        "delete_requested_by": None,
        "delete_request_reason": None,
    })
    log_event(
        firm_id=firm_id,
        event_type="calendar_event.restored",
        entity_type="calendar_event",
        entity_id=event_id,
        actor_type="staff",
        actor_id=current_user.id,
        metadata={},
    )
    return ev


def request_delete(
    db: Session,
    event_id: UUID,
    firm_id: UUID,
    current_user: User,
    reason: Optional[str],
) -> CalendarEvent:
    ev = crud_event.get_event_for_firm(db, event_id, firm_id, include_deleted=False)
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")

    if not _can_view(current_user, ev):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")

    if _is_manager_or_above(current_user):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You can delete this event directly.",
        )

    if ev.owner_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to request deletion of this event.",
        )

    if ev.created_by == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You can delete this event directly.",
        )

    if ev.delete_requested_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A delete request is already pending for this event.",
        )

    now = datetime.now(timezone.utc)
    ev = crud_event.update_event(db, ev, {
        "delete_requested_at": now,
        "delete_requested_by": current_user.id,
        "delete_request_reason": reason,
    })

    log_event(
        firm_id=firm_id,
        event_type="calendar_event.delete_requested",
        entity_type="calendar_event",
        entity_id=event_id,
        actor_type="staff",
        actor_id=current_user.id,
        metadata={"has_reason": reason is not None},
    )

    _notify_delete_request(db, firm_id, ev, current_user)
    return ev


def approve_delete_request(
    db: Session,
    event_id: UUID,
    firm_id: UUID,
    current_user: User,
) -> CalendarEvent:
    ev = crud_event.get_event_for_firm(db, event_id, firm_id, include_deleted=False)
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")
    if ev.delete_requested_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No delete request is pending for this event.",
        )

    had_reason = ev.delete_request_reason is not None
    crud_event.soft_delete_event(db, ev)

    log_event(
        firm_id=firm_id,
        event_type="calendar_event.delete_request_approved",
        entity_type="calendar_event",
        entity_id=event_id,
        actor_type="staff",
        actor_id=current_user.id,
        metadata={"has_reason": had_reason},
    )
    return crud_event.get_event_for_firm(db, event_id, firm_id, include_deleted=True)


def deny_delete_request(
    db: Session,
    event_id: UUID,
    firm_id: UUID,
    current_user: User,
) -> CalendarEvent:
    ev = crud_event.get_event_for_firm(db, event_id, firm_id, include_deleted=False)
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")
    if ev.delete_requested_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No delete request is pending for this event.",
        )

    had_reason = ev.delete_request_reason is not None
    ev = crud_event.update_event(db, ev, {
        "delete_requested_at": None,
        "delete_requested_by": None,
        "delete_request_reason": None,
    })

    log_event(
        firm_id=firm_id,
        event_type="calendar_event.delete_request_denied",
        entity_type="calendar_event",
        entity_id=event_id,
        actor_type="staff",
        actor_id=current_user.id,
        metadata={"has_reason": had_reason},
    )
    return ev
