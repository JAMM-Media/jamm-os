# app/services/booking_service.py

"""
Booking action service: claims a real slot and creates a Booking row.

Responsibility boundary:
  slot_computation_service -- reads: lists available slots for a date range.
  booking_service          -- writes: claims one specific slot, creates the Booking,
                              advances the lead's pipeline stage, fires the event.

Race condition handling:
  This is the first use of SELECT ... FOR UPDATE row-level locking in this codebase.
  Two concurrent requests could both pass an availability re-check performed in
  application code (each sees zero conflicting bookings before either commits).
  WITH the lock, the second concurrent transaction blocks on the locked rows until
  the first commits; it then re-reads the now-committed state and correctly detects
  the conflict. Without the lock, there is a real window between the re-check and
  the INSERT where two requests can both succeed for the same slot.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import BookingStatus, LeadStage
from app.crud.lead import transition_lead_stage
from app.models.booking import Booking
from app.models.lead import Lead
from app.models.user import User
from app.services.behavioral_log import log_event
from app.services.slot_computation_service import (
    ACTIVE_STATUSES,
    get_window_for_day,
    slot_conflicts_with_booking,
)

logger = logging.getLogger(__name__)


def _build_location_snapshot(staff_user: User) -> str | None:
    """Build the location_snapshot string from the staff member's current setting.

    The raw meeting_location_value is stored as-is. The booking confirmation and
    reminder (future tasks) will format it with type context for display. If the
    staff member has not configured a meeting location, returns None -- the
    Booking.location_snapshot field is nullable for this reason.
    """
    return staff_user.meeting_location_value or None


def create_booking(
    db: Session,
    firm_id: UUID,
    lead_id: UUID,
    staff_user_id: UUID,
    start_time: datetime,
    end_time: datetime,
    actor_user_id: UUID,
) -> Booking:
    """Claim a specific slot, create a Booking, transition the lead, and fire the event.

    All writes (booking creation and lead stage transition) are atomic within a
    single transaction. The behavioral event is fired after commit using its own
    session, per the fire-and-forget pattern used throughout the codebase.

    Raises ValueError if:
      - The staff user or lead is not found in the firm.
      - No availability window exists for that day.
      - The daily cap is already reached.
      - The requested slot conflicts with an existing booking's buffer window.
      - The lead's current stage is terminal (won), per transition_lead_stage.
    """
    # Look up staff user (need for location_snapshot + window lookup).
    staff_user = (
        db.query(User)
        .filter(User.id == staff_user_id, User.firm_id == firm_id)
        .first()
    )
    if staff_user is None:
        raise ValueError("Staff user not found in this firm")

    # Look up the lead (needed for transition_lead_stage which takes the object).
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.firm_id == firm_id)
        .first()
    )
    if lead is None:
        raise ValueError("Lead not found in this firm")

    # Fail fast on terminal stage -- before any DB write.
    if lead.stage == LeadStage.won.value:
        raise ValueError(
            "Won is a terminal stage. Cannot book a meeting for a converted lead."
        )

    # Find the availability window for this day of week.
    booking_date: date = start_time.date()
    window = get_window_for_day(db, staff_user_id, firm_id, booking_date.weekday())
    if window is None:
        raise ValueError(
            f"Staff member has no availability window for {booking_date.strftime('%A')}"
        )

    # SELECT FOR UPDATE: lock existing active Booking rows for this staff member on
    # this date. This is the first row-level lock in this codebase. The lock is held
    # until db.commit() (which happens inside transition_lead_stage), so a concurrent
    # request cannot slip through the availability re-check window.
    day_start = datetime.combine(booking_date, datetime.min.time(), tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    existing_bookings = (
        db.query(Booking)
        .filter(
            Booking.staff_user_id == staff_user_id,
            Booking.status.in_(ACTIVE_STATUSES),
            Booking.start_time >= day_start,
            Booking.start_time < day_end,
        )
        .with_for_update()
        .all()
    )

    # Daily cap re-check (against the now-locked, committed state).
    if window.daily_cap is not None and len(existing_bookings) >= window.daily_cap:
        raise ValueError(
            "Daily booking cap is already reached for this staff member on this date"
        )

    # Slot conflict re-check (against the now-locked, committed state).
    for booking in existing_bookings:
        if slot_conflicts_with_booking(
            start_time,
            end_time,
            booking,
            window.buffer_before_minutes,
            window.buffer_after_minutes,
        ):
            raise ValueError(
                f"The requested slot conflicts with an existing booking or its buffer window "
                f"({start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')})"
            )

    # Build location snapshot from the staff member's current setting.
    location_snapshot = _build_location_snapshot(staff_user)

    # Stage the new Booking in the transaction (flush, do not commit yet).
    now = datetime.now(timezone.utc)
    booking = Booking(
        firm_id=firm_id,
        lead_id=lead_id,
        staff_user_id=staff_user_id,
        start_time=start_time,
        end_time=end_time,
        status=BookingStatus.scheduled,
        location_snapshot=location_snapshot,
        created_at=now,
        updated_at=now,
    )
    db.add(booking)
    db.flush()

    # Transition the lead stage and commit. transition_lead_stage calls db.commit()
    # internally, which atomically commits both the booking row and the stage change.
    # Let any ValueError from transition_lead_stage propagate -- a lead that cannot
    # legally transition to call_booked should not have a Booking created for it.
    transition_lead_stage(db, lead, LeadStage.call_booked)

    # Fire the behavioral event after commit, using its own session (fire-and-forget).
    # This event is picked up by _check_goal_jump in the next nurture tick.
    log_event(
        event_type="lead.call_booked",
        firm_id=firm_id,
        entity_type="lead",
        entity_id=lead_id,
        actor_type="staff",
        actor_id=actor_user_id,
        metadata={
            "booking_id": str(booking.id),
            "staff_user_id": str(staff_user_id),
            "start_time": start_time.isoformat(),
        },
    )

    logger.info(
        "booking_service: booking created firm=%s lead=%s staff=%s start=%s",
        firm_id, lead_id, staff_user_id, start_time.isoformat(),
    )
    return booking
