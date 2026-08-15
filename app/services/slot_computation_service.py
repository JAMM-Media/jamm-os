# app/services/slot_computation_service.py

"""
Bookable slot computation for a staff member over a date range.

Given a staff member and a date range, computes the real list of bookable
time slots by applying availability windows, daily caps, and buffer-padded
conflict checks against existing bookings.

Public shared surface (intentionally used by booking_service.py):
  ACTIVE_STATUSES, get_window_for_day, slot_conflicts_with_booking.

All datetimes are UTC-aware. AvailabilityWindow start_time/end_time are
time-of-day (no timezone); they are combined with each calendar date and
treated as UTC, matching the convention used by Booking.start_time/end_time.
No timezone conversion logic is performed here -- that is explicitly out of scope.

Out of scope: caching, timezone conversion, endpoint exposure, unique-per-meeting
video links. Those are future tasks.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import BookingStatus
from app.models.availability_window import AvailabilityWindow
from app.models.booking import Booking

logger = logging.getLogger(__name__)

# Statuses that count as occupying a slot or the daily cap.
# Explicitly excludes 'canceled' -- a canceled booking must not block time
# or count against the cap.
ACTIVE_STATUSES = (BookingStatus.scheduled.value, BookingStatus.completed.value)


def get_window_for_day(
    db: Session,
    staff_user_id: UUID,
    firm_id: UUID,
    day_of_week: int,
) -> Optional[AvailabilityWindow]:
    """Return the availability window for this staff member on this day_of_week, or None."""
    return (
        db.query(AvailabilityWindow)
        .filter(
            AvailabilityWindow.firm_id == firm_id,
            AvailabilityWindow.user_id == staff_user_id,
            AvailabilityWindow.day_of_week == day_of_week,
        )
        .first()
    )


def _get_active_bookings_on_date(
    db: Session,
    staff_user_id: UUID,
    calendar_date: date,
) -> list[Booking]:
    """Return all scheduled/completed bookings for this staff member on the given date.

    Explicitly excludes canceled bookings -- they do not occupy slots or the cap.
    """
    day_start = datetime.combine(calendar_date, datetime.min.time(), tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    return (
        db.query(Booking)
        .filter(
            Booking.staff_user_id == staff_user_id,
            Booking.status.in_(ACTIVE_STATUSES),
            Booking.start_time >= day_start,
            Booking.start_time < day_end,
        )
        .all()
    )


def _generate_candidate_slots(
    window: AvailabilityWindow,
    calendar_date: date,
) -> list[dict]:
    """Chunk the availability window into meeting_duration_minutes increments.

    The last fragment is dropped if it is shorter than a full meeting duration.
    Returns a list of {start_time, end_time} dicts with UTC-aware datetimes.
    """
    duration = timedelta(minutes=window.meeting_duration_minutes)
    window_start = datetime.combine(calendar_date, window.start_time, tzinfo=timezone.utc)
    window_end = datetime.combine(calendar_date, window.end_time, tzinfo=timezone.utc)

    slots = []
    slot_start = window_start
    while slot_start + duration <= window_end:
        slots.append({
            "start_time": slot_start,
            "end_time": slot_start + duration,
        })
        slot_start += duration
    return slots


def slot_conflicts_with_booking(
    slot_start: datetime,
    slot_end: datetime,
    booking: Booking,
    buffer_before_minutes: int,
    buffer_after_minutes: int,
) -> bool:
    """Return True if the slot overlaps the booking's buffer-padded protected window.

    Any overlap at all -- including partial -- discard the slot. This matches
    the strict convention used by established scheduling tools: a partially
    overlapping slot is never offered; it is discarded whole.

    Protected window: [booking.start - buffer_before, booking.end + buffer_after].
    Overlap condition: slot_start < protected_end AND slot_end > protected_start.
    """
    protected_start = booking.start_time - timedelta(minutes=buffer_before_minutes)
    protected_end = booking.end_time + timedelta(minutes=buffer_after_minutes)
    return slot_start < protected_end and slot_end > protected_start


def compute_available_slots(
    db: Session,
    staff_user_id: UUID,
    firm_id: UUID,
    start_date: date,
    end_date: date,
    now: Optional[datetime] = None,
) -> list[dict]:
    """Compute all bookable slots for a staff member over a date range.

    Returns a list of {start_time, end_time} dicts, sorted ascending by start_time.
    All datetimes are UTC-aware.

    Per-day algorithm:
      1. Look up the AvailabilityWindow for this day_of_week. If none, skip the day.
      2. Count active (scheduled/completed) bookings on this date. If count >= daily_cap
         (and daily_cap is not null), skip the entire day.
      3. Generate candidate slots: window chunked into meeting_duration_minutes increments.
         Leftover fragments shorter than one full duration are dropped.
      4. Discard any candidate that conflicts with any active booking's buffer-padded
         protected window (any overlap, not just full containment).
      5. Discard any candidate that starts before now (never offer past slots).

    The now parameter defaults to datetime.now(timezone.utc). Pass an explicit
    value in tests to control the clock.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    all_slots: list[dict] = []
    current_date = start_date

    while current_date <= end_date:
        day_of_week = current_date.weekday()  # 0=Monday, 6=Sunday
        window = get_window_for_day(db, staff_user_id, firm_id, day_of_week)

        if window is None:
            current_date += timedelta(days=1)
            continue

        active_bookings = _get_active_bookings_on_date(db, staff_user_id, current_date)

        # Daily cap check: if already at or above cap, skip the whole day.
        if window.daily_cap is not None and len(active_bookings) >= window.daily_cap:
            logger.debug(
                "slot_computation: daily cap %d reached for user=%s on %s, skipping day",
                window.daily_cap, staff_user_id, current_date,
            )
            current_date += timedelta(days=1)
            continue

        candidates = _generate_candidate_slots(window, current_date)

        for slot in candidates:
            slot_start = slot["start_time"]
            slot_end = slot["end_time"]

            # Skip past slots.
            if slot_start < now:
                continue

            # Conflict check against every active booking on this date.
            conflicted = False
            for booking in active_bookings:
                if slot_conflicts_with_booking(
                    slot_start,
                    slot_end,
                    booking,
                    window.buffer_before_minutes,
                    window.buffer_after_minutes,
                ):
                    conflicted = True
                    break

            if not conflicted:
                all_slots.append(slot)

        current_date += timedelta(days=1)

    return all_slots
