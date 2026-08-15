# app/services/post_call_detection_service.py

"""
Post-call outcome detection service.

Sweeps Booking rows where status == 'scheduled' and end_time < now.
For each past-end booking with no existing outcome-pending Task, creates
a Task assigned to the booking's staff_user_id prompting the staff member
to mark the call outcome (call held, not a fit, or no-show).

Follows the exact pattern of deadline_scheduler.py:
  - Own SessionLocal() in try/finally
  - Idempotency guard before creating any Task
  - Returns summary dict {checked, tasks_created}

Out of scope: outcome branching logic. That is Part B of this build.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.booking import Booking
from app.models.task import Task
from app.core.enums import BookingStatus

logger = logging.getLogger(__name__)


def detect_past_end_bookings() -> dict:
    """Create outcome-pending Tasks for bookings whose end_time has passed.

    Idempotency: if a Task already exists with booking_id == booking.id and
    the same firm_id, no duplicate is created. Safe to run on every scheduler tick.

    Returns {checked: N, tasks_created: N}.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        past_end = db.execute(
            select(Booking).where(
                Booking.status == BookingStatus.scheduled.value,
                Booking.end_time < now,
            )
        ).scalars().all()

        checked = 0
        tasks_created = 0

        for booking in past_end:
            checked += 1

            already_has_task = db.execute(
                select(Task.id).where(
                    Task.booking_id == booking.id,
                    Task.firm_id == booking.firm_id,
                ).limit(1)
            ).first() is not None

            if already_has_task:
                continue

            lead_note = f"Lead ID: {booking.lead_id}\n" if booking.lead_id else ""
            task = Task(
                firm_id=booking.firm_id,
                booking_id=booking.id,
                lead_id=booking.lead_id,
                task_type="internal",
                assigned_to=booking.staff_user_id,
                title=f"Mark call outcome for booking {booking.id}",
                notes=(
                    f"{lead_note}"
                    f"Booking: {booking.start_time.strftime('%Y-%m-%d %H:%M')} UTC "
                    f"to {booking.end_time.strftime('%H:%M')} UTC\n"
                    f"Choose: call held, not a fit, or no-show."
                ),
                status="todo",
                is_self_created=False,
                is_completed=False,
            )
            db.add(task)
            tasks_created += 1
            logger.info(
                "post_call_detection: outcome task created booking=%s firm=%s staff=%s",
                booking.id,
                booking.firm_id,
                booking.staff_user_id,
            )

        db.commit()
        return {"checked": checked, "tasks_created": tasks_created}

    finally:
        db.close()
