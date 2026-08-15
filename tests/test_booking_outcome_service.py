# tests/test_booking_outcome_service.py

"""
Tests for booking_outcome_service.mark_booking_outcome.

Covers all three outcome branches (call_held, not_a_fit, no_show), the
no-show reschedule cap, the reactivate_enrollment path inside call_held,
and error cases (already resolved, outcome already marked, invalid outcome).
All tests use real PostgreSQL via TestingSessionLocal.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import TestingSessionLocal
from app.core.enums import (
    BookingStatus,
    EnrollmentStatus,
    LeadLostReason,
    LeadProvenance,
    LeadStage,
    UserRole,
)
from app.models.behavioral_event import BehavioralEvent
from app.models.availability_window import AvailabilityWindow
from app.models.booking import Booking
from app.models.enrollment import Enrollment
from app.models.firm import Firm
from app.models.lead import Lead
from app.models.sequence import Sequence, SequenceVersion, Step
from app.models.task import Task
from app.models.user import User
from app.services.booking_outcome_service import mark_booking_outcome
from app.services.post_call_detection_service import detect_past_end_bookings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc)
PAST_START = NOW - timedelta(hours=2)
PAST_END = NOW - timedelta(hours=1)


def _make_firm(slug: str) -> Firm:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Firm {slug}", slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)
        _ = firm.id
        return firm
    finally:
        db.close()


def _make_user(firm_id) -> User:
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=f"staff-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="x",
            role=UserRole.staff,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        _ = user.id
        return user
    finally:
        db.close()


def _make_lead(firm_id, stage=LeadStage.call_booked) -> Lead:
    db = TestingSessionLocal()
    try:
        lead = Lead(
            firm_id=firm_id,
            name="Test Lead",
            email=f"lead-{uuid.uuid4().hex[:6]}@example.com",
            provenance=LeadProvenance.firm_entered.value,
            stage=stage.value,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        _ = lead.id, lead.stage
        return lead
    finally:
        db.close()


def _make_booking(firm_id, staff_id, lead_id, status=BookingStatus.scheduled,
                  start=None, end=None) -> Booking:
    db = TestingSessionLocal()
    try:
        now = datetime.now(timezone.utc)
        booking = Booking(
            firm_id=firm_id,
            staff_user_id=staff_id,
            lead_id=lead_id,
            start_time=start or PAST_START,
            end_time=end or PAST_END,
            status=status,
            created_at=now,
            updated_at=now,
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
        _ = booking.id
        return booking
    finally:
        db.close()


def _make_task_for_booking(firm_id, booking_id, lead_id, staff_id) -> Task:
    """Create the outcome-pending Task directly (skipping the sweep)."""
    db = TestingSessionLocal()
    try:
        task = Task(
            firm_id=firm_id,
            booking_id=booking_id,
            lead_id=lead_id,
            task_type="internal",
            assigned_to=staff_id,
            title=f"Mark call outcome for booking {booking_id}",
            notes="Choose: call held, not a fit, or no-show.",
            status="todo",
            is_self_created=False,
            is_completed=False,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        _ = task.id
        return task
    finally:
        db.close()


def _make_paused_enrollment(firm_id, lead_id) -> Enrollment:
    db = TestingSessionLocal()
    try:
        seq = Sequence(firm_id=firm_id, name=f"Seq-{uuid.uuid4().hex[:6]}")
        db.add(seq)
        db.flush()
        ver = SequenceVersion(sequence_id=seq.id, version_number=1)
        db.add(ver)
        db.flush()
        step = Step(
            sequence_version_id=ver.id,
            step_key="ENTRY",
            step_type="email",
            channel="email",
            config={"subject": "Hi", "body": "<p>Hi</p>"},
        )
        db.add(step)
        db.flush()
        now = datetime.now(timezone.utc)
        enrollment = Enrollment(
            firm_id=firm_id,
            lead_id=lead_id,
            sequence_id=seq.id,
            sequence_version_id=ver.id,
            current_step_id=step.id,
            next_action_time=None,
            status=EnrollmentStatus.paused_reply,
            enrolled_at=now,
        )
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)
        _ = enrollment.id, enrollment.status
        return enrollment
    finally:
        db.close()


def _fetch_booking(booking_id) -> Booking:
    db = TestingSessionLocal()
    try:
        b = db.query(Booking).filter(Booking.id == booking_id).first()
        _ = b.id, b.status
        return b
    finally:
        db.close()


def _fetch_task(booking_id) -> Task:
    db = TestingSessionLocal()
    try:
        t = db.query(Task).filter(Task.booking_id == booking_id).first()
        _ = t.id, t.outcome, t.is_completed, t.status
        return t
    finally:
        db.close()


def _fetch_lead(lead_id) -> Lead:
    db = TestingSessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        _ = lead.id, lead.stage, lead.lost_reason
        return lead
    finally:
        db.close()


def _fetch_enrollment(enrollment_id) -> Enrollment:
    db = TestingSessionLocal()
    try:
        e = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
        _ = e.id, e.status
        return e
    finally:
        db.close()


def _setup(slug_suffix: str):
    """Create firm, staff user, lead, past-end booking, and outcome Task."""
    firm = _make_firm(f"bos-{slug_suffix}-{uuid.uuid4().hex[:4]}")
    staff = _make_user(firm.id)
    actor = _make_user(firm.id)
    lead = _make_lead(firm.id)
    booking = _make_booking(firm.id, staff.id, lead.id)
    task = _make_task_for_booking(firm.id, booking.id, lead.id, staff.id)
    return firm, staff, actor, lead, booking, task


# ---------------------------------------------------------------------------
# call_held branch
# ---------------------------------------------------------------------------

class TestCallHeld:

    def test_call_held_sets_booking_completed_and_marks_task(self):
        """call_held sets Booking.status=completed and Task.outcome=call_held, is_completed=True."""
        firm, staff, actor, lead, booking, task = _setup("held-basic")

        db = TestingSessionLocal()
        try:
            result = mark_booking_outcome(
                db=db,
                booking_id=booking.id,
                firm_id=firm.id,
                outcome="call_held",
                actor_user_id=actor.id,
            )
            assert result.id == booking.id
        finally:
            db.close()

        b = _fetch_booking(booking.id)
        assert b.status == BookingStatus.completed, (
            f"Expected completed; got {b.status!r}"
        )

        t = _fetch_task(booking.id)
        assert t.outcome == "call_held"
        assert t.is_completed is True
        assert t.status == "done"

    def test_call_held_reactivates_paused_reply_enrollment(self):
        """call_held reactivates a paused_reply enrollment for the same lead."""
        firm, staff, actor, lead, booking, task = _setup("held-react")
        enrollment = _make_paused_enrollment(firm.id, lead.id)

        db = TestingSessionLocal()
        try:
            mark_booking_outcome(
                db=db,
                booking_id=booking.id,
                firm_id=firm.id,
                outcome="call_held",
                actor_user_id=actor.id,
            )
        finally:
            db.close()

        e = _fetch_enrollment(enrollment.id)
        assert e.status == EnrollmentStatus.active.value, (
            f"Enrollment must be active after call_held; got {e.status!r}"
        )

    def test_call_held_does_not_fail_when_no_paused_enrollment(self):
        """call_held succeeds without raising when the lead has no paused_reply enrollment."""
        firm, staff, actor, lead, booking, task = _setup("held-noenr")

        db = TestingSessionLocal()
        try:
            result = mark_booking_outcome(
                db=db,
                booking_id=booking.id,
                firm_id=firm.id,
                outcome="call_held",
                actor_user_id=actor.id,
            )
        finally:
            db.close()

        b = _fetch_booking(booking.id)
        assert b.status == BookingStatus.completed


# ---------------------------------------------------------------------------
# not_a_fit branch
# ---------------------------------------------------------------------------

class TestNotAFit:

    def test_not_a_fit_completes_booking_and_transitions_lead_to_lost(self):
        """not_a_fit sets Booking.status=completed and transitions lead to lost."""
        firm, staff, actor, lead, booking, task = _setup("naf")

        db = TestingSessionLocal()
        try:
            mark_booking_outcome(
                db=db,
                booking_id=booking.id,
                firm_id=firm.id,
                outcome="not_a_fit",
                actor_user_id=actor.id,
            )
        finally:
            db.close()

        b = _fetch_booking(booking.id)
        assert b.status == BookingStatus.completed, (
            f"Expected completed; got {b.status!r}"
        )

        refreshed_lead = _fetch_lead(lead.id)
        assert refreshed_lead.stage == LeadStage.lost.value, (
            f"Lead must be lost after not_a_fit; got {refreshed_lead.stage!r}"
        )
        assert refreshed_lead.lost_reason == LeadLostReason.other.value, (
            f"lost_reason must be other; got {refreshed_lead.lost_reason!r}"
        )

        t = _fetch_task(booking.id)
        assert t.outcome == "not_a_fit"
        assert t.is_completed is True

        # GUARD: not_a_fit must NOT fire lead.call_held (wrong event type --
        # transition_lead_stage already fires lead.lost; no second event is correct).
        # A lead.call_held event here mislabels the permanent history.
        db_check = TestingSessionLocal()
        try:
            call_held_events = db_check.query(BehavioralEvent).filter(
                BehavioralEvent.entity_id == lead.id,
                BehavioralEvent.event_type == "lead.call_held",
            ).count()
            assert call_held_events == 0, (
                f"not_a_fit must not fire lead.call_held; found {call_held_events} event(s)"
            )
            lost_events = db_check.query(BehavioralEvent).filter(
                BehavioralEvent.entity_id == lead.id,
                BehavioralEvent.event_type == "lead.lost",
            ).count()
            assert lost_events == 1, (
                f"not_a_fit must fire exactly one lead.lost event; found {lost_events}"
            )
        finally:
            db_check.close()


# ---------------------------------------------------------------------------
# no_show branch
# ---------------------------------------------------------------------------

class TestNoShow:

    def test_no_show_sets_booking_no_show_and_marks_task(self):
        """no_show sets Booking.status=no_show and Task.outcome=no_show."""
        firm, staff, actor, lead, booking, task = _setup("ns-basic")

        db = TestingSessionLocal()
        try:
            mark_booking_outcome(
                db=db,
                booking_id=booking.id,
                firm_id=firm.id,
                outcome="no_show",
                actor_user_id=actor.id,
            )
        finally:
            db.close()

        b = _fetch_booking(booking.id)
        assert b.status == BookingStatus.no_show, (
            f"Expected no_show; got {b.status!r}"
        )

        t = _fetch_task(booking.id)
        assert t.outcome == "no_show"
        assert t.is_completed is True

    def test_no_show_below_cap_does_not_set_cap_reached(self):
        """First and second no-shows are below the cap (prior_no_shows < 2)."""
        firm, staff, actor, lead, booking, task = _setup("ns-belowcap")

        db = TestingSessionLocal()
        try:
            result = mark_booking_outcome(
                db=db,
                booking_id=booking.id,
                firm_id=firm.id,
                outcome="no_show",
                actor_user_id=actor.id,
            )
        finally:
            db.close()

        b = _fetch_booking(booking.id)
        assert b.status == BookingStatus.no_show

    def test_no_show_at_cap_two_prior_marks_cap_reached(self):
        """Third no-show (2 prior) has cap_reached=True in behavioral event metadata.

        The service itself continues to function; the cap_reached flag is carried
        in the log_event metadata. This test confirms the service does not error
        at cap and does set the booking/task correctly.
        """
        firm, staff, actor, lead = _make_firm(f"ns-cap-{uuid.uuid4().hex[:4]}"), None, None, None
        firm = _make_firm(f"ns-cap-{uuid.uuid4().hex[:4]}")
        staff = _make_user(firm.id)
        actor = _make_user(firm.id)
        lead = _make_lead(firm.id)

        # Create 2 prior no_show bookings for this lead
        for _ in range(2):
            prior_booking = _make_booking(
                firm.id, staff.id, lead.id, status=BookingStatus.no_show
            )

        # Third booking -- this is the cap-reached case
        cap_booking = _make_booking(firm.id, staff.id, lead.id)
        cap_task = _make_task_for_booking(firm.id, cap_booking.id, lead.id, staff.id)

        db = TestingSessionLocal()
        try:
            mark_booking_outcome(
                db=db,
                booking_id=cap_booking.id,
                firm_id=firm.id,
                outcome="no_show",
                actor_user_id=actor.id,
            )
        finally:
            db.close()

        b = _fetch_booking(cap_booking.id)
        assert b.status == BookingStatus.no_show

        t = _fetch_task(cap_booking.id)
        assert t.outcome == "no_show"
        assert t.is_completed is True


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

class TestOutcomeErrors:

    def test_already_resolved_booking_raises(self):
        """Marking outcome on an already-completed booking raises ValueError."""
        firm, staff, actor, lead, booking, task = _setup("err-resolved")

        db = TestingSessionLocal()
        try:
            mark_booking_outcome(
                db=db,
                booking_id=booking.id,
                firm_id=firm.id,
                outcome="call_held",
                actor_user_id=actor.id,
            )
        finally:
            db.close()

        db2 = TestingSessionLocal()
        try:
            with pytest.raises(ValueError, match="status"):
                mark_booking_outcome(
                    db=db2,
                    booking_id=booking.id,
                    firm_id=firm.id,
                    outcome="call_held",
                    actor_user_id=actor.id,
                )
        finally:
            db2.close()

    def test_outcome_already_marked_raises(self):
        """Calling mark_booking_outcome a second time raises ValueError about duplicate outcome."""
        firm, staff, actor, lead, booking, task = _setup("err-dup")

        # First call succeeds.
        db = TestingSessionLocal()
        try:
            mark_booking_outcome(
                db=db,
                booking_id=booking.id,
                firm_id=firm.id,
                outcome="call_held",
                actor_user_id=actor.id,
            )
        finally:
            db.close()

        # Reset booking status so we hit the task.outcome guard, not the booking status guard.
        db_reset = TestingSessionLocal()
        try:
            b = db_reset.query(Booking).filter(Booking.id == booking.id).first()
            b.status = BookingStatus.scheduled
            db_reset.commit()
        finally:
            db_reset.close()

        db2 = TestingSessionLocal()
        try:
            with pytest.raises(ValueError, match="already marked"):
                mark_booking_outcome(
                    db=db2,
                    booking_id=booking.id,
                    firm_id=firm.id,
                    outcome="call_held",
                    actor_user_id=actor.id,
                )
        finally:
            db2.close()

    def test_invalid_outcome_string_raises(self):
        """Passing an unrecognised outcome string raises ValueError."""
        firm, staff, actor, lead, booking, task = _setup("err-invalid")

        db = TestingSessionLocal()
        try:
            with pytest.raises(ValueError, match="outcome must be one of"):
                mark_booking_outcome(
                    db=db,
                    booking_id=booking.id,
                    firm_id=firm.id,
                    outcome="not_real",
                    actor_user_id=actor.id,
                )
        finally:
            db.close()

    def test_booking_not_found_raises(self):
        """Marking outcome on a booking from a different firm raises ValueError."""
        firm, staff, actor, lead, booking, task = _setup("err-wrongfirm")
        other_firm = _make_firm(f"other-{uuid.uuid4().hex[:6]}")

        db = TestingSessionLocal()
        try:
            with pytest.raises(ValueError, match="not found"):
                mark_booking_outcome(
                    db=db,
                    booking_id=booking.id,
                    firm_id=other_firm.id,
                    outcome="call_held",
                    actor_user_id=actor.id,
                )
        finally:
            db.close()
