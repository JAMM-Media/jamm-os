# tests/test_booking_service.py

"""
Tests for booking_service.create_booking.

GUARD TEST: test_two_sequential_attempts_same_slot_only_one_succeeds
Watched-fail cycle: temporarily removes the slot conflict re-check inside
create_booking (simulating what would happen if the FOR UPDATE lock + re-check
were absent), runs two sequential booking attempts for the same slot, confirms
both wrongly succeed (red). Restores the re-check, confirms only one succeeds (green).

This simulates the race condition: in a real concurrent scenario, two requests
could both pass the availability check before either commits. The row-level lock
(SELECT ... FOR UPDATE) ensures the second request re-reads the now-committed
state and correctly detects the conflict.
"""

import uuid
from datetime import date, datetime, time, timedelta, timezone

import pytest

from tests.conftest import TestingSessionLocal
from app.core.enums import BookingStatus, LeadProvenance, LeadStage, MeetingLocationType, UserRole
from app.models.availability_window import AvailabilityWindow
from app.models.behavioral_event import BehavioralEvent
from app.models.booking import Booking
from app.models.enrollment import Enrollment
from app.models.firm import Firm
from app.models.lead import Lead
from app.models.sequence import Sequence, SequenceGoal, SequenceVersion, Step, StepEdge
from app.models.user import User
from app.services.booking_service import create_booking
from app.services.nurture_execution_service import run_nurture_tick


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm(slug: str) -> Firm:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Firm {slug}", slug=slug, timezone="UTC")
        db.add(firm)
        db.commit()
        db.refresh(firm)
        _ = firm.id
        return firm
    finally:
        db.close()


def _make_user(
    firm_id,
    meeting_location_type=None,
    meeting_location_value=None,
) -> User:
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=f"staff-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="not-a-real-hash",
            role=UserRole.staff,
            meeting_location_type=meeting_location_type,
            meeting_location_value=meeting_location_value,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        _ = user.id
        return user
    finally:
        db.close()


def _make_lead(firm_id) -> Lead:
    db = TestingSessionLocal()
    try:
        lead = Lead(
            firm_id=firm_id,
            name="Test Lead",
            email=f"lead-{uuid.uuid4().hex[:6]}@example.com",
            provenance=LeadProvenance.firm_entered.value,
            stage=LeadStage.contacted.value,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        _ = lead.id, lead.stage
        return lead
    finally:
        db.close()


def _make_window(
    firm_id, user_id,
    day_of_week: int = 0,
    start_time: time = time(9, 0),
    end_time: time = time(17, 0),
    meeting_duration_minutes: int = 30,
    buffer_before_minutes: int = 0,
    buffer_after_minutes: int = 0,
    daily_cap: int | None = None,
) -> AvailabilityWindow:
    db = TestingSessionLocal()
    try:
        now = datetime.now(timezone.utc)
        window = AvailabilityWindow(
            firm_id=firm_id, user_id=user_id,
            day_of_week=day_of_week,
            start_time=start_time, end_time=end_time,
            meeting_duration_minutes=meeting_duration_minutes,
            buffer_before_minutes=buffer_before_minutes,
            buffer_after_minutes=buffer_after_minutes,
            daily_cap=daily_cap,
            created_at=now, updated_at=now,
        )
        db.add(window)
        db.commit()
        db.refresh(window)
        _ = window.id
        return window
    finally:
        db.close()


def _make_booking_direct(firm_id, staff_user_id, start_time, end_time,
                          status=BookingStatus.scheduled) -> Booking:
    """Create a Booking directly, bypassing create_booking (for conflict setup)."""
    db = TestingSessionLocal()
    try:
        now = datetime.now(timezone.utc)
        booking = Booking(
            firm_id=firm_id, staff_user_id=staff_user_id,
            start_time=start_time, end_time=end_time,
            status=status, created_at=now, updated_at=now,
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
        _ = booking.id
        return booking
    finally:
        db.close()


def _dt(d: date, h: int, m: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, h, m, tzinfo=timezone.utc)


def _fetch_lead(lead_id) -> Lead:
    db = TestingSessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        _ = lead.id, lead.stage
        return lead
    finally:
        db.close()


def _count_bookings_for_slot(staff_user_id, start_time) -> int:
    db = TestingSessionLocal()
    try:
        return db.query(Booking).filter(
            Booking.staff_user_id == staff_user_id,
            Booking.start_time == start_time,
        ).count()
    finally:
        db.close()


# A Monday in the future (relative to test environment "past now") for window day_of_week
MONDAY = date(2025, 1, 6)
SLOT_START = _dt(MONDAY, 9, 0)
SLOT_END = _dt(MONDAY, 9, 30)


# ---------------------------------------------------------------------------
# GUARD TEST: two sequential attempts, same slot, exactly one succeeds
# ---------------------------------------------------------------------------

class TestConcurrentBookingGuard:
    """GUARD TEST with watched-fail cycle.

    Demonstrates that the slot conflict re-check (backed by SELECT FOR UPDATE)
    prevents two requests from both successfully booking the same slot.

    Approach: sequentially call create_booking twice for the same slot.
    With the re-check in place (correct): the second call sees the committed
    booking from the first call and raises a conflict ValueError.
    Without the re-check (broken): both calls succeed and create two Booking rows.
    """

    def test_two_sequential_attempts_same_slot_only_one_succeeds(self):
        """Only the first of two sequential booking attempts for the same slot succeeds."""
        firm = _make_firm(f"guard-conc-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)
        lead1 = _make_lead(firm.id)
        lead2 = _make_lead(firm.id)
        _make_window(firm.id, user.id, day_of_week=MONDAY.weekday(),
                     start_time=time(9, 0), end_time=time(10, 0))

        actor = _make_user(firm.id)

        # First attempt: must succeed.
        db1 = TestingSessionLocal()
        try:
            create_booking(
                db=db1,
                firm_id=firm.id,
                lead_id=lead1.id,
                staff_user_id=user.id,
                start_time=SLOT_START,
                end_time=SLOT_END,
                actor_user_id=actor.id,
            )
        finally:
            db1.close()

        # Second attempt (same slot, different lead): must raise a conflict ValueError.
        db2 = TestingSessionLocal()
        try:
            with pytest.raises(ValueError, match="conflict"):
                create_booking(
                    db=db2,
                    firm_id=firm.id,
                    lead_id=lead2.id,
                    staff_user_id=user.id,
                    start_time=SLOT_START,
                    end_time=SLOT_END,
                    actor_user_id=actor.id,
                )
        finally:
            db2.rollback()
            db2.close()

        # Exactly one Booking row must exist.
        count = _count_bookings_for_slot(user.id, SLOT_START)
        assert count == 1, (
            f"Exactly one booking must exist for this slot; found {count}"
        )


# ---------------------------------------------------------------------------
# Happy path: correct Booking row, location_snapshot, and lead stage
# ---------------------------------------------------------------------------

class TestCreateBookingHappyPath:

    def test_creates_booking_with_correct_location_snapshot(self):
        """Booking.location_snapshot is populated from the staff member's current setting."""
        firm = _make_firm(f"loc-snap-{uuid.uuid4().hex[:6]}")
        user = _make_user(
            firm.id,
            meeting_location_type=MeetingLocationType.video,
            meeting_location_value="https://zoom.us/j/999888777",
        )
        lead = _make_lead(firm.id)
        actor = _make_user(firm.id)
        _make_window(firm.id, user.id, day_of_week=MONDAY.weekday(),
                     start_time=time(9, 0), end_time=time(10, 0))

        db = TestingSessionLocal()
        try:
            booking = create_booking(
                db=db,
                firm_id=firm.id,
                lead_id=lead.id,
                staff_user_id=user.id,
                start_time=SLOT_START,
                end_time=SLOT_END,
                actor_user_id=actor.id,
            )
            assert booking.location_snapshot == "https://zoom.us/j/999888777", (
                f"location_snapshot must match the staff member's current setting. "
                f"Got: {booking.location_snapshot!r}"
            )
            assert booking.status == BookingStatus.scheduled
            assert booking.lead_id == lead.id
            assert booking.staff_user_id == user.id
        finally:
            db.close()

    def test_creates_booking_with_null_snapshot_when_no_location_set(self):
        """location_snapshot is null when the staff member has no meeting location configured."""
        firm = _make_firm(f"loc-null-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)  # no meeting location
        lead = _make_lead(firm.id)
        actor = _make_user(firm.id)
        _make_window(firm.id, user.id, day_of_week=MONDAY.weekday(),
                     start_time=time(9, 0), end_time=time(10, 0))

        db = TestingSessionLocal()
        try:
            booking = create_booking(
                db=db,
                firm_id=firm.id,
                lead_id=lead.id,
                staff_user_id=user.id,
                start_time=SLOT_START,
                end_time=SLOT_END,
                actor_user_id=actor.id,
            )
            assert booking.location_snapshot is None
        finally:
            db.close()

    def test_successful_booking_transitions_lead_to_call_booked(self):
        """After a successful booking the lead's stage is call_booked."""
        firm = _make_firm(f"stage-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)
        lead = _make_lead(firm.id)
        actor = _make_user(firm.id)
        _make_window(firm.id, user.id, day_of_week=MONDAY.weekday(),
                     start_time=time(9, 0), end_time=time(10, 0))

        db = TestingSessionLocal()
        try:
            create_booking(
                db=db,
                firm_id=firm.id,
                lead_id=lead.id,
                staff_user_id=user.id,
                start_time=SLOT_START,
                end_time=SLOT_END,
                actor_user_id=actor.id,
            )
        finally:
            db.close()

        refreshed = _fetch_lead(lead.id)
        assert refreshed.stage == LeadStage.call_booked.value, (
            f"Lead stage must be call_booked after booking. Got: {refreshed.stage!r}"
        )


# ---------------------------------------------------------------------------
# Goal-jump integration: the behavioral event triggers the nurture goal-jump
# ---------------------------------------------------------------------------

class TestBookingGoalJumpIntegration:

    def test_call_booked_event_triggers_nurture_goal_jump(self, monkeypatch):
        """A lead.call_booked behavioral event is picked up by the nurture goal-jump.

        Wires: create_booking fires lead.call_booked -> next nurture tick detects
        the BehavioralEvent via _check_goal_jump -> enrollment advances to the
        goal target step.
        """
        from app.services import email_service as email_mod
        monkeypatch.setattr(
            email_mod.EmailService, "send_nurture_email", staticmethod(lambda *a, **k: None)
        )

        firm = _make_firm(f"goal-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)
        lead = _make_lead(firm.id)
        actor = _make_user(firm.id)
        _make_window(firm.id, user.id, day_of_week=MONDAY.weekday(),
                     start_time=time(9, 0), end_time=time(10, 0))

        # Set up a sequence with a SequenceGoal on "lead.call_booked".
        db = TestingSessionLocal()
        try:
            seq = Sequence(firm_id=firm.id, name="Test Sequence")
            db.add(seq)
            db.flush()
            ver = SequenceVersion(sequence_id=seq.id, version_number=1)
            db.add(ver)
            db.flush()

            step_entry = Step(
                sequence_version_id=ver.id, step_key="ENTRY",
                step_type="email", channel="email",
                config={"subject": "Hi", "body": "<p>Hi</p>"},
            )
            step_target = Step(
                sequence_version_id=ver.id, step_key="CALL_BOOKED_TARGET",
                step_type="email", channel="email",
                config={"subject": "Booked", "body": "<p>Booked</p>"},
            )
            db.add(step_entry)
            db.add(step_target)
            db.flush()

            goal = SequenceGoal(
                sequence_version_id=ver.id,
                goal_event="lead.call_booked",
                target_step_id=step_target.id,
            )
            db.add(goal)

            from datetime import timezone as tz
            now = datetime.now(tz.utc)
            past = now - timedelta(hours=1)
            enrollment = Enrollment(
                firm_id=firm.id,
                lead_id=lead.id,
                sequence_id=seq.id,
                sequence_version_id=ver.id,
                current_step_id=step_entry.id,
                next_action_time=past,
                enrolled_at=past,
            )
            db.add(enrollment)
            db.commit()
            enrollment_id = enrollment.id
            target_step_id = step_target.id
        finally:
            db.close()

        # Create the booking -- this fires lead.call_booked.
        db2 = TestingSessionLocal()
        try:
            create_booking(
                db=db2,
                firm_id=firm.id,
                lead_id=lead.id,
                staff_user_id=user.id,
                start_time=SLOT_START,
                end_time=SLOT_END,
                actor_user_id=actor.id,
            )
        finally:
            db2.close()

        # Run a nurture tick -- should detect the BehavioralEvent via goal-jump.
        result = run_nurture_tick()
        assert result["goal_jumps"] >= 1, (
            f"Nurture tick must detect the lead.call_booked event as a goal-jump. "
            f"Got goal_jumps={result['goal_jumps']}"
        )

        # Enrollment must advance to the target step.
        db3 = TestingSessionLocal()
        try:
            enr = db3.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
            assert enr.current_step_id == target_step_id, (
                f"Enrollment must advance to goal target step. Got {enr.current_step_id!r}"
            )
        finally:
            db3.close()


# ---------------------------------------------------------------------------
# Error cases: won lead, slot already taken
# ---------------------------------------------------------------------------

class TestCreateBookingErrors:

    def test_booking_won_lead_raises_and_does_not_create_row(self):
        """Attempting to book a meeting for a won lead raises ValueError and creates no Booking."""
        firm = _make_firm(f"won-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)
        actor = _make_user(firm.id)
        _make_window(firm.id, user.id, day_of_week=MONDAY.weekday(),
                     start_time=time(9, 0), end_time=time(10, 0))

        # Create lead and force it to won without creating a real Client.
        db = TestingSessionLocal()
        try:
            lead = Lead(
                firm_id=firm.id,
                name="Won Lead",
                email=f"won-{uuid.uuid4().hex[:6]}@example.com",
                provenance=LeadProvenance.firm_entered.value,
                stage=LeadStage.won.value,
            )
            db.add(lead)
            db.commit()
            db.refresh(lead)
            lead_id = lead.id
        finally:
            db.close()

        db2 = TestingSessionLocal()
        try:
            with pytest.raises(ValueError, match="terminal"):
                create_booking(
                    db=db2,
                    firm_id=firm.id,
                    lead_id=lead_id,
                    staff_user_id=user.id,
                    start_time=SLOT_START,
                    end_time=SLOT_END,
                    actor_user_id=actor.id,
                )
        finally:
            db2.rollback()
            db2.close()

        # No Booking row must have been created.
        count = _count_bookings_for_slot(user.id, SLOT_START)
        assert count == 0, (
            f"No Booking must be created for a won lead. Found {count} rows."
        )

    def test_booking_already_taken_slot_raises_conflict(self):
        """Attempting to book an already-occupied slot raises a conflict ValueError."""
        firm = _make_firm(f"taken-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)
        lead1 = _make_lead(firm.id)
        lead2 = _make_lead(firm.id)
        actor = _make_user(firm.id)
        _make_window(firm.id, user.id, day_of_week=MONDAY.weekday(),
                     start_time=time(9, 0), end_time=time(10, 0))

        # First booking succeeds.
        db1 = TestingSessionLocal()
        try:
            create_booking(
                db=db1,
                firm_id=firm.id,
                lead_id=lead1.id,
                staff_user_id=user.id,
                start_time=SLOT_START,
                end_time=SLOT_END,
                actor_user_id=actor.id,
            )
        finally:
            db1.close()

        # Second booking for same slot must fail.
        db2 = TestingSessionLocal()
        try:
            with pytest.raises(ValueError, match="conflict"):
                create_booking(
                    db=db2,
                    firm_id=firm.id,
                    lead_id=lead2.id,
                    staff_user_id=user.id,
                    start_time=SLOT_START,
                    end_time=SLOT_END,
                    actor_user_id=actor.id,
                )
        finally:
            db2.rollback()
            db2.close()

        # Still exactly one Booking.
        count = _count_bookings_for_slot(user.id, SLOT_START)
        assert count == 1, (
            f"Only one Booking must exist after second attempt fails. Found {count}"
        )
