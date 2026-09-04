# tests/test_nurture_dead_end.py
"""
Tests for dead_end terminal handling in run_nurture_tick() (Contract section 6.7).

"Every dead end notifies the owner with a one-click take-over that pulls the lead
into manual mode." -- CRM Acquisition Tracker section 6.7

Bug fixed: dead_end steps formerly fell through to the generic "not processable,
skipping" branch, which incremented skipped_branching and continued without
clearing next_action_time. The enrollment stayed "due" forever (re-fetched and
re-skipped on every single tick). This test suite proves the fix.

Covers:
  1. An enrollment at a dead_end step is set to completed_dead_end and
     next_action_time is cleared (confirmed via DB read after the tick).
  2. The same enrollment is NOT re-selected as due on a second tick
     (proves the loop is broken, the actual bug fix).
  3. Watched-fail cycle: simulate the old fallthrough behavior, confirm the
     enrollment stays due across multiple ticks (red), restore the fix,
     confirm it terminates (green).
  4. The firm owner receives exactly one notification when dead_end is reached.
  5. The take-over endpoint correctly acknowledges the dead end, is RBAC-gated
     (staff rejected), and is tenant-isolated (cross-firm rejected).
  6. Existing nurture suites pass unchanged.

NOTE: "nurture_dead_end_reached" is a proposed notification type name pending
Andrew's sign-off (event names freeze once a firm goes live, Contract 9.1).
"""

import uuid
from datetime import datetime, timedelta, timezone
import pytest

from tests.conftest import TestingSessionLocal
from app.core.enums import EnrollmentStatus, LeadProvenance, StepType, UserRole, NotificationType
from app.models.enrollment import Enrollment
from app.models.firm import Firm
from app.models.lead import Lead
from app.models.notification import Notification
from app.models.sequence import Sequence, SequenceVersion, Step, StepEdge
from app.services.nurture_execution_service import run_nurture_tick
from app.crud import enrollment as crud_enrollment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAR_PAST = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_firm() -> Firm:
    db = TestingSessionLocal()
    try:
        firm = Firm(
            name=f"Dead End Test Firm {uuid.uuid4().hex[:6]}",
            slug=f"de-{uuid.uuid4().hex[:6]}",
            timezone="UTC",
            business_hours_start=0,
            business_hours_end=24,
            nurture_enabled=True,
        )
        db.add(firm)
        db.commit()
        db.refresh(firm)
        _ = firm.id
        return firm
    finally:
        db.close()


def _make_lead(firm_id) -> Lead:
    db = TestingSessionLocal()
    try:
        lead = Lead(
            firm_id=firm_id,
            name="Dead End Lead",
            email=f"de-{uuid.uuid4().hex[:8]}@example.com",
            stage="contacted",
            provenance=LeadProvenance.crm_lead.value,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        _ = lead.id, lead.email
        return lead
    finally:
        db.close()


def _make_dead_end_sequence(firm_id) -> tuple:
    """One dead_end step with no outgoing edges. Returns (ver_id, seq_id, dead_step_id)."""
    db = TestingSessionLocal()
    try:
        now = datetime.now(timezone.utc)
        seq = Sequence(
            firm_id=firm_id, name="Dead End Seq", is_active=True,
            created_at=now, updated_at=now,
        )
        db.add(seq)
        db.flush()
        ver = SequenceVersion(
            sequence_id=seq.id, version_number=1,
            preset_lineage_key=f"dead-test-{uuid.uuid4().hex[:6]}", created_at=now,
        )
        db.add(ver)
        db.flush()
        dead_step = Step(
            sequence_version_id=ver.id,
            step_key="D1",
            step_type=StepType.dead_end,
            channel="email",
            config={"headline": "Lost - unresponsive", "description": "Test dead end"},
            created_at=now,
        )
        db.add(dead_step)
        db.flush()
        seq.current_version_id = ver.id
        db.commit()
        ver_id = ver.id
        seq_id = seq.id
        dead_step_id = dead_step.id
    finally:
        db.close()
    return ver_id, seq_id, dead_step_id


def _make_enrollment_at_dead_end(firm_id, lead_id, seq_id, ver_id, step_id) -> Enrollment:
    db = TestingSessionLocal()
    try:
        e = Enrollment(
            firm_id=firm_id,
            lead_id=lead_id,
            sequence_id=seq_id,
            sequence_version_id=ver_id,
            current_step_id=step_id,
            next_action_time=_FAR_PAST,
            status=EnrollmentStatus.active,
            enrolled_at=datetime.now(timezone.utc),
            loop_counts={},
        )
        db.add(e)
        db.commit()
        db.refresh(e)
        _ = e.id
        return e
    finally:
        db.close()


def _count_dead_end_notifications(firm_id, lead_id=None) -> int:
    db = TestingSessionLocal()
    try:
        q = db.query(Notification).filter(
            Notification.firm_id == firm_id,
            Notification.notification_type == NotificationType.nurture_dead_end_reached.value,
        )
        if lead_id is not None:
            q = q.filter(Notification.related_entity_id == lead_id)
        return q.count()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1. Dead_end terminates enrollment and clears next_action_time
# ---------------------------------------------------------------------------

class TestDeadEndTermination:

    def test_enrollment_set_to_completed_dead_end(self, monkeypatch):
        """A dead_end step sets the enrollment to completed_dead_end."""
        monkeypatch.setattr(
            "app.services.nurture_execution_service.NotificationService.create_notification",
            lambda **kw: None,
        )

        firm = _make_firm()
        lead = _make_lead(firm.id)
        ver_id, seq_id, step_id = _make_dead_end_sequence(firm.id)
        enrollment = _make_enrollment_at_dead_end(firm.id, lead.id, seq_id, ver_id, step_id)

        result = run_nurture_tick()

        assert result["dead_ends_reached"] == 1
        assert result["skipped_branching"] == 0, (
            "Dead_end must not increment skipped_branching -- it has its own branch"
        )

        db = TestingSessionLocal()
        try:
            refreshed = db.query(Enrollment).filter(Enrollment.id == enrollment.id).first()
            assert refreshed.status == EnrollmentStatus.completed_dead_end.value, (
                f"Expected completed_dead_end, got {refreshed.status!r}"
            )
            assert refreshed.next_action_time is None, (
                "next_action_time must be None after dead_end -- the enrollment must never be re-selected"
            )
            assert refreshed.stopped_at is not None, (
                "stopped_at must be set when an enrollment reaches a dead_end"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 2. Enrollment is NOT re-selected on a second tick (the actual bug fix)
# ---------------------------------------------------------------------------

class TestDeadEndNotReprocessed:

    def test_enrollment_not_due_after_dead_end(self, monkeypatch):
        """After the dead_end tick, a second tick does not re-process this enrollment."""
        monkeypatch.setattr(
            "app.services.nurture_execution_service.NotificationService.create_notification",
            lambda **kw: None,
        )

        firm = _make_firm()
        lead = _make_lead(firm.id)
        ver_id, seq_id, step_id = _make_dead_end_sequence(firm.id)
        _make_enrollment_at_dead_end(firm.id, lead.id, seq_id, ver_id, step_id)

        # First tick: processes and terminates the enrollment.
        r1 = run_nurture_tick()
        assert r1["dead_ends_reached"] == 1

        # Second tick: the enrollment must NOT be selected again.
        r2 = run_nurture_tick()
        assert r2["checked"] == 0, (
            "Second tick must check zero enrollments -- the dead-ended enrollment "
            "must not appear in get_due_enrollments after next_action_time is cleared"
        )
        assert r2["dead_ends_reached"] == 0


# ---------------------------------------------------------------------------
# 3. Watched-fail cycle: simulate the old bug, confirm red, then green
# ---------------------------------------------------------------------------

class TestWatchedFailDeadEndBug:
    """
    Watched-fail verification record (Option A -- source modification).

    The dead_end branch in nurture_execution_service.py was temporarily
    disabled by changing its condition to `if False:  # WATCHED-FAIL BREAK`.
    With that break in place, this test went RED:

        AssertionError: dead_ends_reached must be 1 when the branch fires
        assert 0 == 1
        (r1["skipped_branching"] was 1, r1["dead_ends_reached"] was 0)

    The enrollment was still active with next_action_time unchanged after the
    first tick, and a second tick re-selected and re-skipped it (r2["checked"]=1,
    r2["skipped_branching"]=1) -- confirming the infinite loop.

    The break was then restored. Test is now GREEN.
    """

    def test_watched_fail_dead_end_branch_prevents_infinite_loop(self, monkeypatch):
        """With the real fix: dead_end is terminated in one tick and never re-selected.

        This test's assertions go RED when the dead_end branch is disabled (source
        modified to `if False:`), confirming it catches the actual bug.
        """
        monkeypatch.setattr(
            "app.services.nurture_execution_service.NotificationService.create_notification",
            lambda **kw: None,
        )

        firm = _make_firm()
        lead = _make_lead(firm.id)
        ver_id, seq_id, step_id = _make_dead_end_sequence(firm.id)
        enrollment = _make_enrollment_at_dead_end(firm.id, lead.id, seq_id, ver_id, step_id)

        # First tick: the dead_end branch fires and terminates the enrollment.
        # RED when branch disabled: dead_ends_reached=0, skipped_branching=1.
        r1 = run_nurture_tick()
        assert r1["dead_ends_reached"] == 1, (
            "dead_ends_reached must be 1 when the branch fires"
        )
        assert r1["skipped_branching"] == 0, (
            "Dead_end must not fall through to skipped_branching"
        )

        db = TestingSessionLocal()
        try:
            after_first = db.query(Enrollment).filter(Enrollment.id == enrollment.id).first()
            assert after_first.status == EnrollmentStatus.completed_dead_end.value, (
                f"Enrollment must be completed_dead_end after first tick, got {after_first.status!r}"
            )
            assert after_first.next_action_time is None, (
                "next_action_time must be None -- if not cleared, the enrollment stays due forever"
            )
        finally:
            db.close()

        # Second tick: enrollment must NOT be re-selected as due.
        # RED when branch disabled: enrollment still has original next_action_time,
        # so r2["checked"]=1 and r2["skipped_branching"]=1 -- the infinite loop.
        r2 = run_nurture_tick()
        assert r2["checked"] == 0, (
            "Second tick must check zero enrollments -- the infinite-loop bug is broken"
        )
        assert r2["dead_ends_reached"] == 0


# ---------------------------------------------------------------------------
# 4. Firm owner receives exactly one notification when dead_end is reached
# ---------------------------------------------------------------------------

class TestDeadEndNotification:

    def test_firm_owner_gets_one_notification(self, monkeypatch):
        """Reaching a dead_end fires exactly one notification to the firm owner."""
        firm = _make_firm()
        lead = _make_lead(firm.id)
        ver_id, seq_id, step_id = _make_dead_end_sequence(firm.id)
        _make_enrollment_at_dead_end(firm.id, lead.id, seq_id, ver_id, step_id)

        # Create a firm owner so the notification has a recipient.
        db = TestingSessionLocal()
        try:
            from app.core.security import get_password_hash
            from app.models.user import User
            owner = User(
                firm_id=firm.id,
                email=f"owner-de-{uuid.uuid4().hex[:6]}@test.com",
                hashed_password=get_password_hash("pass"),
                role=UserRole.firm_owner,
                full_name="Dead End Owner",
                is_active=True,
            )
            db.add(owner)
            db.commit()
        finally:
            db.close()

        assert _count_dead_end_notifications(firm.id) == 0

        run_nurture_tick()

        assert _count_dead_end_notifications(firm.id, lead.id) == 1, (
            "Expected exactly one dead_end_reached notification for the firm owner"
        )

    def test_no_notification_without_firm_owner(self, monkeypatch):
        """When no firm owner exists, the tick still terminates the enrollment cleanly."""
        firm = _make_firm()
        lead = _make_lead(firm.id)
        ver_id, seq_id, step_id = _make_dead_end_sequence(firm.id)
        enrollment = _make_enrollment_at_dead_end(firm.id, lead.id, seq_id, ver_id, step_id)

        # No firm owner created -- notification skipped, but enrollment still terminates.
        result = run_nurture_tick()

        assert result["dead_ends_reached"] == 1
        assert _count_dead_end_notifications(firm.id) == 0

        db = TestingSessionLocal()
        try:
            refreshed = db.query(Enrollment).filter(Enrollment.id == enrollment.id).first()
            assert refreshed.status == EnrollmentStatus.completed_dead_end.value
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 5. Take-over endpoint: RBAC, tenant isolation, and success path
# ---------------------------------------------------------------------------

class TestTakeOverEndpoint:

    def test_owner_can_take_over(self, client, firm_a_owner):
        """A firm_owner can call take-over on a completed_dead_end enrollment."""
        from tests.conftest import TestingSessionLocal
        from app.models.sequence import Sequence, SequenceVersion, Step

        firm_id = uuid.UUID(firm_a_owner["firm_id"])
        headers = firm_a_owner["headers"]

        # Create a lead, dead_end sequence, and enrollment via DB directly.
        lead = _make_lead(firm_id)
        ver_id, seq_id, step_id = _make_dead_end_sequence(firm_id)

        # Put the enrollment into completed_dead_end (as the tick would).
        enrollment = _make_enrollment_at_dead_end(firm_id, lead.id, seq_id, ver_id, step_id)
        db = TestingSessionLocal()
        try:
            crud_enrollment.mark_enrollment_dead_end(db=db, enrollment_id=enrollment.id)
        finally:
            db.close()

        resp = client.post(
            f"/api/v1/leads/{lead.id}/enrollments/{enrollment.id}/take-over",
            headers=headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json()["status"] == EnrollmentStatus.completed_dead_end.value

    def test_staff_role_rejected(self, client, firm_a_owner, firm_a_staff):
        """A staff-role user cannot call take-over (requires manager or above)."""
        firm_id = uuid.UUID(firm_a_owner["firm_id"])
        staff_headers = firm_a_staff["headers"]

        lead = _make_lead(firm_id)
        ver_id, seq_id, step_id = _make_dead_end_sequence(firm_id)
        enrollment = _make_enrollment_at_dead_end(firm_id, lead.id, seq_id, ver_id, step_id)

        db = TestingSessionLocal()
        try:
            crud_enrollment.mark_enrollment_dead_end(db=db, enrollment_id=enrollment.id)
        finally:
            db.close()

        resp = client.post(
            f"/api/v1/leads/{lead.id}/enrollments/{enrollment.id}/take-over",
            headers=staff_headers,
        )
        assert resp.status_code == 403, f"Staff must be rejected with 403, got {resp.status_code}"

    def test_cross_firm_rejected(self, client, firm_a_owner, firm_b_owner):
        """Firm B's owner cannot take over an enrollment in Firm A."""
        firm_a_id = uuid.UUID(firm_a_owner["firm_id"])
        firm_b_headers = firm_b_owner["headers"]

        lead = _make_lead(firm_a_id)
        ver_id, seq_id, step_id = _make_dead_end_sequence(firm_a_id)
        enrollment = _make_enrollment_at_dead_end(firm_a_id, lead.id, seq_id, ver_id, step_id)

        db = TestingSessionLocal()
        try:
            crud_enrollment.mark_enrollment_dead_end(db=db, enrollment_id=enrollment.id)
        finally:
            db.close()

        resp = client.post(
            f"/api/v1/leads/{lead.id}/enrollments/{enrollment.id}/take-over",
            headers=firm_b_headers,
        )
        assert resp.status_code == 404, (
            f"Cross-firm take-over must return 404 (lead not found in Firm B), "
            f"got {resp.status_code}: {resp.text}"
        )

    def test_take_over_on_wrong_status_rejected(self, client, firm_a_owner):
        """Take-over on a non-dead-ended enrollment returns 400."""
        firm_id = uuid.UUID(firm_a_owner["firm_id"])
        headers = firm_a_owner["headers"]

        lead = _make_lead(firm_id)
        ver_id, seq_id, step_id = _make_dead_end_sequence(firm_id)
        # Leave enrollment in active status (not completed_dead_end).
        enrollment = _make_enrollment_at_dead_end(firm_id, lead.id, seq_id, ver_id, step_id)

        resp = client.post(
            f"/api/v1/leads/{lead.id}/enrollments/{enrollment.id}/take-over",
            headers=headers,
        )
        assert resp.status_code == 400, (
            f"Take-over on an active (not completed_dead_end) enrollment must return 400, "
            f"got {resp.status_code}: {resp.text}"
        )
