# app/services/booking_outcome_service.py

"""
Booking outcome marking service.

Called by the POST /api/v1/bookings/{booking_id}/outcome endpoint after the
staff member records what happened on the call. Three outcomes are supported:

  call_held  -- the call took place; continue the sequence (reactivate if paused_reply)
  not_a_fit  -- the call took place; lead is not a fit; transition to lost
  no_show    -- lead did not appear; fire call_no_show event; check reschedule cap

No-show reschedule cap: the contract states the loop is capped at 2 reschedule
attempts. The cap is enforced by counting prior no_show Booking rows for this
lead BEFORE marking the current booking. If prior_no_shows >= 2, cap_reached is
included in the behavioral event metadata so the front end and intelligence layer
can handle it -- this endpoint does not currently take any additional action
beyond that, because the contract does not specify what happens at cap reached
beyond "capped at 2." That is a confirmed open design question, surfaced here
rather than invented.

Finding: LeadLostReason has no 'not_a_fit' value. The not_a_fit branch uses
LeadLostReason.other as the closest match. A dedicated enum value should be
added to LeadLostReason in a future task, once Andrew blesses the final set.
"""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import BookingStatus, EnrollmentStatus, LeadLostReason, LeadStage
from app.crud.enrollment import reactivate_enrollment
from app.crud.lead import transition_lead_stage
from app.models.booking import Booking
from app.models.enrollment import Enrollment
from app.models.lead import Lead
from app.models.task import Task
from app.services.behavioral_log import log_event

logger = logging.getLogger(__name__)

VALID_OUTCOMES = frozenset({"call_held", "not_a_fit", "no_show"})

# Count of prior no_show bookings for this lead at which no further reschedule
# is offered. Prior = 0 -> first no-show, reschedule allowed.
# Prior = 1 -> second no-show, reschedule allowed.
# Prior >= 2 -> cap reached, cap_reached=True in the event.
_RESCHEDULE_CAP = 2


def mark_booking_outcome(
    db: Session,
    booking_id: UUID,
    firm_id: UUID,
    outcome: str,
    actor_user_id: UUID,
) -> Booking:
    """Record the call outcome for a past-end booking.

    Validates that the booking is scheduled (not already resolved) and that
    the corresponding outcome Task has not already been marked. Applies the
    appropriate branch and fires the behavioral event.

    Raises ValueError for: invalid outcome string, booking not found, booking
    already resolved, task not found, outcome already marked, lead not found.
    Caller converts ValueError to HTTP 400.
    """
    if outcome not in VALID_OUTCOMES:
        raise ValueError(
            f"outcome must be one of: {', '.join(sorted(VALID_OUTCOMES))}"
        )

    booking = db.query(Booking).filter(
        Booking.id == booking_id,
        Booking.firm_id == firm_id,
    ).first()
    if booking is None:
        raise ValueError("Booking not found in this firm")
    if booking.status != BookingStatus.scheduled.value:
        raise ValueError(
            f"Cannot mark outcome on a booking with status '{booking.status}': "
            f"only scheduled bookings can have an outcome recorded"
        )

    task = db.query(Task).filter(
        Task.booking_id == booking_id,
        Task.firm_id == firm_id,
    ).first()
    if task is None:
        raise ValueError(
            "No outcome task found for this booking. "
            "The post-call detection sweep may not have run yet."
        )
    if task.outcome is not None:
        raise ValueError(
            f"Outcome already marked as '{task.outcome}' for this booking"
        )

    lead = None
    if booking.lead_id is not None:
        lead = db.query(Lead).filter(
            Lead.id == booking.lead_id,
            Lead.firm_id == firm_id,
        ).first()

    if outcome == "call_held":
        _apply_call_held(db, booking, task, lead, actor_user_id, firm_id)
    elif outcome == "not_a_fit":
        _apply_not_a_fit(db, booking, task, lead, actor_user_id, firm_id)
    else:
        _apply_no_show(db, booking, task, lead, actor_user_id, firm_id)

    return booking


def _apply_call_held(
    db: Session,
    booking: Booking,
    task: Task,
    lead: Lead | None,
    actor_user_id: UUID,
    firm_id: UUID,
) -> None:
    booking.status = BookingStatus.completed
    task.outcome = "call_held"
    task.is_completed = True
    task.status = "done"
    db.commit()

    if lead is not None:
        paused = db.query(Enrollment).filter(
            Enrollment.lead_id == lead.id,
            Enrollment.firm_id == firm_id,
            Enrollment.status == EnrollmentStatus.paused_reply.value,
        ).first()
        if paused is not None:
            reactivate_enrollment(db, paused.id, firm_id)

    log_event(
        event_type="lead.call_held",
        firm_id=firm_id,
        entity_type="lead",
        entity_id=lead.id if lead else booking.lead_id,
        actor_type="staff",
        actor_id=actor_user_id,
        metadata={"booking_id": str(booking.id)},
    )
    logger.info(
        "booking_outcome: call_held booking=%s firm=%s lead=%s",
        booking.id, firm_id, booking.lead_id,
    )


def _apply_not_a_fit(
    db: Session,
    booking: Booking,
    task: Task,
    lead: Lead | None,
    actor_user_id: UUID,
    firm_id: UUID,
) -> None:
    booking.status = BookingStatus.completed
    task.outcome = "not_a_fit"
    task.is_completed = True
    task.status = "done"
    db.flush()

    if lead is not None:
        # transition_lead_stage commits internally; this atomically commits the
        # booking/task flush above plus the lead stage change in one transaction.
        # lost_reason=other: no 'not_a_fit' value exists in LeadLostReason;
        # other is the closest match. See module docstring for the open finding.
        # transition_lead_stage fires lead.lost -- that is the complete behavioral
        # record of this outcome. Section 9.1 has no dedicated event for a
        # not_a_fit call outcome, so no additional log_event call is made here.
        transition_lead_stage(
            db, lead, LeadStage.lost, lost_reason=LeadLostReason.other
        )

    logger.info(
        "booking_outcome: not_a_fit booking=%s firm=%s lead=%s",
        booking.id, firm_id, booking.lead_id,
    )


def _apply_no_show(
    db: Session,
    booking: Booking,
    task: Task,
    lead: Lead | None,
    actor_user_id: UUID,
    firm_id: UUID,
) -> None:
    prior_no_shows = 0
    if booking.lead_id is not None:
        prior_no_shows = db.query(Booking).filter(
            Booking.lead_id == booking.lead_id,
            Booking.firm_id == firm_id,
            Booking.status == BookingStatus.no_show.value,
        ).count()

    cap_reached = prior_no_shows >= _RESCHEDULE_CAP

    booking.status = BookingStatus.no_show
    task.outcome = "no_show"
    task.is_completed = True
    task.status = "done"
    db.commit()

    log_event(
        event_type="lead.call_no_show",
        firm_id=firm_id,
        entity_type="lead",
        entity_id=lead.id if lead else booking.lead_id,
        actor_type="staff",
        actor_id=actor_user_id,
        metadata={
            "booking_id": str(booking.id),
            "prior_no_shows": prior_no_shows,
            "cap_reached": cap_reached,
        },
    )
    logger.info(
        "booking_outcome: no_show booking=%s firm=%s lead=%s prior=%d cap_reached=%s",
        booking.id, firm_id, booking.lead_id, prior_no_shows, cap_reached,
    )
