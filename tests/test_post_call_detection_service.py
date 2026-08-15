# tests/test_post_call_detection_service.py

"""
Tests for post_call_detection_service.detect_past_end_bookings and
crud.enrollment.reactivate_enrollment.

All tests use real PostgreSQL via TestingSessionLocal -- no mocks.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import TestingSessionLocal
from app.core.enums import BookingStatus, EnrollmentStatus, LeadProvenance, LeadStage, UserRole
from app.models.booking import Booking
from app.models.enrollment import Enrollment
from app.models.firm import Firm
from app.models.lead import Lead
from app.models.sequence import Sequence, SequenceVersion, Step
from app.models.task import Task
from app.models.user import User
from app.crud.enrollment import reactivate_enrollment
from app.services.post_call_detection_service import detect_past_end_bookings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
            hashed_password="not-a-real-hash",
            role=UserRole.staff,
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
            stage=LeadStage.call_booked.value,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        _ = lead.id
        return lead
    finally:
        db.close()


def _make_booking(
    firm_id,
    staff_user_id,
    lead_id,
    start_time: datetime,
    end_time: datetime,
    status: BookingStatus = BookingStatus.scheduled,
) -> Booking:
    db = TestingSessionLocal()
    try:
        now = datetime.now(timezone.utc)
        booking = Booking(
            firm_id=firm_id,
            staff_user_id=staff_user_id,
            lead_id=lead_id,
            start_time=start_time,
            end_time=end_time,
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


def _make_enrollment_paused(firm_id, lead_id) -> Enrollment:
    """Create a minimal paused_reply enrollment via a real sequence."""
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


def _task_count_for_booking(booking_id) -> int:
    db = TestingSessionLocal()
    try:
        return db.query(Task).filter(Task.booking_id == booking_id).count()
    finally:
        db.close()


def _fetch_enrollment(enrollment_id) -> Enrollment:
    db = TestingSessionLocal()
    try:
        enr = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
        _ = enr.id, enr.status
        return enr
    finally:
        db.close()


NOW = datetime.now(timezone.utc)
PAST_START = NOW - timedelta(hours=2)
PAST_END = NOW - timedelta(hours=1)
FUTURE_START = NOW + timedelta(hours=1)
FUTURE_END = NOW + timedelta(hours=2)


# ---------------------------------------------------------------------------
# detect_past_end_bookings: core sweep behaviour
# ---------------------------------------------------------------------------

class TestDetectPastEndBookings:

    def test_past_end_scheduled_booking_creates_one_task(self):
        """A scheduled booking whose end_time is in the past gets exactly one outcome Task."""
        firm = _make_firm(f"pcd-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)
        lead = _make_lead(firm.id)
        booking = _make_booking(firm.id, user.id, lead.id, PAST_START, PAST_END)

        result = detect_past_end_bookings()

        assert result["tasks_created"] >= 1
        count = _task_count_for_booking(booking.id)
        assert count == 1, f"Expected exactly 1 outcome task; found {count}"

        db = TestingSessionLocal()
        try:
            task = db.query(Task).filter(Task.booking_id == booking.id).first()
            assert task is not None
            assert task.firm_id == firm.id
            assert task.assigned_to == user.id
            assert task.lead_id == lead.id
            assert task.task_type == "internal"
            assert task.status == "todo"
            assert task.is_completed is False
        finally:
            db.close()

    def test_sweep_twice_does_not_create_duplicate_task(self):
        """Running the sweep a second time does not create a second Task for the same booking."""
        firm = _make_firm(f"pcd-idem-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)
        lead = _make_lead(firm.id)
        booking = _make_booking(firm.id, user.id, lead.id, PAST_START, PAST_END)

        result1 = detect_past_end_bookings()
        assert result1["tasks_created"] >= 1
        count_after_first = _task_count_for_booking(booking.id)
        assert count_after_first == 1, f"First sweep: expected 1 task; found {count_after_first}"

        result2 = detect_past_end_bookings()
        count_after_second = _task_count_for_booking(booking.id)
        assert count_after_second == 1, (
            f"Second sweep must not create a duplicate; found {count_after_second}"
        )

    def test_future_booking_does_not_create_task(self):
        """A booking whose end_time is in the future is not touched by the sweep."""
        firm = _make_firm(f"pcd-fut-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)
        lead = _make_lead(firm.id)
        booking = _make_booking(firm.id, user.id, lead.id, FUTURE_START, FUTURE_END)

        detect_past_end_bookings()

        count = _task_count_for_booking(booking.id)
        assert count == 0, f"Future booking must not get an outcome task; found {count}"

    def test_non_scheduled_past_booking_is_ignored(self):
        """A past booking already marked completed or no_show is not re-processed."""
        firm = _make_firm(f"pcd-done-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)
        lead = _make_lead(firm.id)

        for status in (BookingStatus.completed, BookingStatus.no_show, BookingStatus.canceled):
            booking = _make_booking(
                firm.id, user.id, lead.id, PAST_START, PAST_END, status=status
            )
            detect_past_end_bookings()
            count = _task_count_for_booking(booking.id)
            assert count == 0, (
                f"Booking with status={status.value} must not get an outcome task; found {count}"
            )


# ---------------------------------------------------------------------------
# reactivate_enrollment
# ---------------------------------------------------------------------------

class TestReactivateEnrollment:

    def test_reactivates_paused_reply_enrollment(self):
        """reactivate_enrollment moves a paused_reply enrollment back to active."""
        firm = _make_firm(f"react-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        enrollment = _make_enrollment_paused(firm.id, lead.id)

        db = TestingSessionLocal()
        try:
            result = reactivate_enrollment(db, enrollment.id, firm.id)
            assert result.status == EnrollmentStatus.active.value, (
                f"Expected active after reactivate; got {result.status!r}"
            )
        finally:
            db.close()

        refreshed = _fetch_enrollment(enrollment.id)
        assert refreshed.status == EnrollmentStatus.active.value, (
            f"Persisted status must be active; got {refreshed.status!r}"
        )

    def test_reactivate_already_active_raises(self):
        """Calling reactivate_enrollment on an already-active enrollment raises ValueError."""
        firm = _make_firm(f"react-active-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        db_setup = TestingSessionLocal()
        try:
            seq = Sequence(firm_id=firm.id, name=f"Seq-{uuid.uuid4().hex[:6]}")
            db_setup.add(seq)
            db_setup.flush()
            ver = SequenceVersion(sequence_id=seq.id, version_number=1)
            db_setup.add(ver)
            db_setup.flush()
            step = Step(
                sequence_version_id=ver.id,
                step_key="ENTRY",
                step_type="email",
                channel="email",
                config={"subject": "Hi", "body": "<p>Hi</p>"},
            )
            db_setup.add(step)
            db_setup.flush()
            now = datetime.now(timezone.utc)
            enrollment = Enrollment(
                firm_id=firm.id,
                lead_id=lead.id,
                sequence_id=seq.id,
                sequence_version_id=ver.id,
                current_step_id=step.id,
                next_action_time=None,
                status=EnrollmentStatus.active,
                enrolled_at=now,
            )
            db_setup.add(enrollment)
            db_setup.commit()
            enrollment_id = enrollment.id
        finally:
            db_setup.close()

        db = TestingSessionLocal()
        try:
            with pytest.raises(ValueError, match="paused_reply"):
                reactivate_enrollment(db, enrollment_id, firm.id)
        finally:
            db.close()

    def test_reactivate_wrong_firm_raises(self):
        """reactivate_enrollment raises ValueError if enrollment is not in the given firm."""
        firm = _make_firm(f"react-firm-{uuid.uuid4().hex[:6]}")
        other_firm = _make_firm(f"react-other-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        enrollment = _make_enrollment_paused(firm.id, lead.id)

        db = TestingSessionLocal()
        try:
            with pytest.raises(ValueError, match="not found"):
                reactivate_enrollment(db, enrollment.id, other_firm.id)
        finally:
            db.close()
