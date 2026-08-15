# app/crud/availability_window.py

import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, Query

from app.models.availability_window import AvailabilityWindow
from app.schemas.availability_window import AvailabilityWindowCreate, AvailabilityWindowUpdate


def get_windows_for_user(
    db: Session,
    user_id: uuid.UUID,
    firm_id: uuid.UUID,
) -> list[AvailabilityWindow]:
    """All windows for one staff member, scoped to the firm."""
    return (
        db.query(AvailabilityWindow)
        .filter(
            AvailabilityWindow.firm_id == firm_id,
            AvailabilityWindow.user_id == user_id,
        )
        .order_by(AvailabilityWindow.day_of_week)
        .all()
    )


def get_windows_for_firm_query(
    db: Session,
    firm_id: uuid.UUID,
) -> Query:
    """SQLAlchemy Query of all windows across the firm, for use with paginate()."""
    return (
        db.query(AvailabilityWindow)
        .filter(AvailabilityWindow.firm_id == firm_id)
        .order_by(AvailabilityWindow.user_id, AvailabilityWindow.day_of_week)
    )


def get_window(
    db: Session,
    window_id: uuid.UUID,
    firm_id: uuid.UUID,
) -> Optional[AvailabilityWindow]:
    """Single window by id, tenant-scoped."""
    return (
        db.query(AvailabilityWindow)
        .filter(
            AvailabilityWindow.id == window_id,
            AvailabilityWindow.firm_id == firm_id,
        )
        .first()
    )


def create_window(
    db: Session,
    user_id: uuid.UUID,
    firm_id: uuid.UUID,
    window_in: AvailabilityWindowCreate,
) -> AvailabilityWindow:
    """Create one availability window.

    Raises ValueError if a window already exists for this user on this day_of_week
    (enforced by uq_availability_window_user_day). The router catches ValueError
    and returns a 409 response rather than letting a raw IntegrityError escape.
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    window = AvailabilityWindow(
        id=uuid.uuid4(),
        firm_id=firm_id,
        user_id=user_id,
        day_of_week=window_in.day_of_week,
        start_time=window_in.start_time,
        end_time=window_in.end_time,
        buffer_before_minutes=window_in.buffer_before_minutes,
        buffer_after_minutes=window_in.buffer_after_minutes,
        meeting_duration_minutes=window_in.meeting_duration_minutes,
        daily_cap=window_in.daily_cap,
        created_at=now,
        updated_at=now,
    )
    db.add(window)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # Only convert unique-constraint violations (23505) to ValueError.
        # FK violations (23503) and other integrity errors are re-raised
        # so the router does not misreport them as duplicate-day conflicts.
        pgcode = getattr(getattr(exc, "orig", None), "pgcode", None)
        if pgcode == "23505":
            raise ValueError(
                f"A window already exists for this user on day_of_week {window_in.day_of_week}"
            )
        raise
    db.refresh(window)
    return window


def update_window(
    db: Session,
    window_id: uuid.UUID,
    firm_id: uuid.UUID,
    window_in: AvailabilityWindowUpdate,
) -> Optional[AvailabilityWindow]:
    """Update fields on an existing window. Returns None if not found.

    Raises ValueError if the update produces a duplicate (user_id, day_of_week).
    """
    from datetime import datetime, timezone
    window = get_window(db, window_id, firm_id)
    if window is None:
        return None
    for field, value in window_in.model_dump(exclude_unset=True).items():
        setattr(window, field, value)
    window.updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(
            f"A window already exists for this user on day_of_week {window_in.day_of_week}"
        )
    db.refresh(window)
    return window


def delete_window(
    db: Session,
    window_id: uuid.UUID,
    firm_id: uuid.UUID,
) -> bool:
    """Delete a window. Returns True if deleted, False if not found."""
    window = get_window(db, window_id, firm_id)
    if window is None:
        return False
    db.delete(window)
    db.commit()
    return True
