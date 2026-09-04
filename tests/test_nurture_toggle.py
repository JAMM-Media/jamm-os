# tests/test_nurture_toggle.py
"""
Guard tests for the nurture pause/go system:
  1. Per-firm toggle off: enrollment for a toggle-off firm is untouched.
  2. Environment kill switch off: even with firm toggle on, nothing fires.
  3. Resume re-basing: flipping the toggle to true via PATCH /firms/me rebases
     stale wait_fixed next_action_time to now rather than leaving it in the past.
  4. firm.nurture_toggled fires on both false->true and true->false transitions.
  5. Toggle-off firm's enrollments are excluded at the query level.
  6. Business hours and hold_for_approval still apply when toggle is true.

WATCHED-FAIL PROCEDURE (per How_We_Work_Process_Rules.md section 2):
For each guard test below, break the thing being guarded, confirm red, restore,
confirm green, confirm git diff matches. Records are in the commit message.
"""

import uuid
from datetime import datetime, timezone, timedelta

import pytest

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.lead import Lead
from app.models.user import User
from app.models.sequence import Sequence, SequenceVersion, Step, StepEdge
from app.models.enrollment import Enrollment
from app.core.enums import LeadProvenance, EnrollmentStatus, StepType, UserRole
from app.core.security import get_password_hash
from app.crud.enrollment import get_due_enrollments
from app.services.nurture_execution_service import run_nurture_tick, _compute_next_action_time


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_firm(nurture_enabled: bool = True) -> Firm:
    slug = f"toggle-test-{uuid.uuid4().hex[:8]}"
    db = TestingSessionLocal()
    try:
        firm = Firm(
            name=f"Toggle Test Firm {slug}",
            slug=slug,
            timezone="UTC",
            business_hours_start=0,
            business_hours_end=24,
            nurture_enabled=nurture_enabled,
        )
        db.add(firm)
        db.commit()
        db.refresh(firm)
        _ = firm.id
        return firm
    finally:
        db.close()


def _make_firm_with_owner(nurture_enabled: bool = True):
    """Returns (firm, user) -- user is a firm_owner in that firm."""
    slug = f"toggle-owner-{uuid.uuid4().hex[:8]}"
    db = TestingSessionLocal()
    try:
        firm = Firm(
            name=f"Toggle Owner Firm {slug}",
            slug=slug,
            timezone="UTC",
            business_hours_start=0,
            business_hours_end=24,
            nurture_enabled=nurture_enabled,
        )
        db.add(firm)
        db.flush()
        user = User(
            firm_id=firm.id,
            email=f"owner-{uuid.uuid4().hex[:6]}@toggletest.com",
            hashed_password=get_password_hash("testpass123"),
            full_name="Toggle Test Owner",
            role=UserRole.firm_owner,
        )
        db.add(user)
        db.commit()
        db.refresh(firm)
        db.refresh(user)
        _ = firm.id, user.id, user.email
        return firm, user
    finally:
        db.close()


def _make_lead(firm_id) -> Lead:
    db = TestingSessionLocal()
    try:
        lead = Lead(
            firm_id=firm_id,
            name="Toggle Test Lead",
            email=f"toggle-{uuid.uuid4().hex[:8]}@example.com",
            provenance=LeadProvenance.firm_entered.value,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        _ = lead.id
        return lead
    finally:
        db.close()


def _make_sequence_with_email_step(firm_id):
    """Returns (sequence_id, version_id, step_id) for a one-node email sequence."""
    db = TestingSessionLocal()
    try:
        seq = Sequence(firm_id=firm_id, name="Toggle Test Sequence")
        db.add(seq)
        db.flush()
        ver = SequenceVersion(sequence_id=seq.id, version_number=1)
        db.add(ver)
        db.flush()
        step = Step(
            sequence_version_id=ver.id,
            step_key="s1",
            step_type=StepType.email.value,
            channel="email",
            config={"subject": "Toggle Subject", "body": "<p>Toggle body</p>"},
        )
        db.add(step)
        db.commit()
        db.refresh(seq)
        db.refresh(ver)
        db.refresh(step)
        _ = seq.id, ver.id, step.id
        return seq.id, ver.id, step.id
    finally:
        db.close()


def _make_wait_fixed_step(firm_id, duration_seconds: int = 3600):
    """Returns (sequence_id, version_id, step_id) for a wait_fixed step."""
    db = TestingSessionLocal()
    try:
        seq = Sequence(firm_id=firm_id, name="Wait Fixed Sequence")
        db.add(seq)
        db.flush()
        ver = SequenceVersion(sequence_id=seq.id, version_number=1)
        db.add(ver)
        db.flush()
        step = Step(
            sequence_version_id=ver.id,
            step_key="w1",
            step_type=StepType.wait_fixed.value,
            channel="email",
            config={"duration_seconds": duration_seconds},
        )
        db.add(step)
        db.commit()
        db.refresh(seq)
        db.refresh(ver)
        db.refresh(step)
        _ = seq.id, ver.id, step.id
        return seq.id, ver.id, step.id
    finally:
        db.close()


def _make_enrollment(firm_id, lead_id, sequence_id, version_id, step_id=None, next_action_time=None) -> Enrollment:
    db = TestingSessionLocal()
    try:
        enr = Enrollment(
            firm_id=firm_id,
            lead_id=lead_id,
            sequence_id=sequence_id,
            sequence_version_id=version_id,
            current_step_id=step_id,
            next_action_time=next_action_time or datetime.now(timezone.utc) - timedelta(minutes=1),
            status=EnrollmentStatus.active.value,
            loop_counts={},
        )
        db.add(enr)
        db.commit()
        db.refresh(enr)
        _ = enr.id
        return enr
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Guard test 1: per-firm toggle off blocks at query level
#
# BREAK: Set firm.nurture_enabled = True in _make_firm(nurture_enabled=False) call.
# EXPECTED RED: result["checked"] > 0, enrollment is processed.
# RESTORE: revert to nurture_enabled=False.
# CONFIRM GREEN: result["checked"] == 0, enrollment untouched.
# ---------------------------------------------------------------------------

class TestToggleOffFirmSendsNothing:

    def test_toggle_off_firm_enrollment_not_processed(self, monkeypatch):
        """Enrollment for a toggle-off firm is never loaded or processed."""
        firm = _make_firm(nurture_enabled=False)
        lead = _make_lead(firm.id)
        seq_id, ver_id, step_id = _make_sequence_with_email_step(firm.id)
        now = datetime.now(timezone.utc)
        enr = _make_enrollment(
            firm.id, lead.id, seq_id, ver_id, step_id,
            next_action_time=now - timedelta(minutes=5),
        )

        send_calls = []
        monkeypatch.setattr(
            "app.services.nurture_execution_service.EmailService.send_nurture_email",
            lambda **kw: send_calls.append(kw),
        )

        result = run_nurture_tick()

        assert result["checked"] == 0, (
            f"Expected 0 checked for toggle-off firm, got {result['checked']}"
        )
        assert result["sent"] == 0, f"Expected 0 sent, got {result['sent']}"
        assert len(send_calls) == 0, "send_nurture_email must not be called for toggle-off firm"

        db = TestingSessionLocal()
        try:
            refreshed = db.query(Enrollment).filter(Enrollment.id == enr.id).first()
            assert refreshed.next_action_time == enr.next_action_time, (
                "next_action_time must not change for toggle-off firm"
            )
            assert refreshed.status == EnrollmentStatus.active.value, (
                "status must remain active (enrollment is held, not cancelled)"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Guard test 2: environment kill switch off blocks all firms
#
# BREAK: Change the patched NURTURE_SENDS_ENABLED to True.
# EXPECTED RED: tick proceeds, enrollment is processed.
# RESTORE: revert to False.
# CONFIRM GREEN: result["checked"] == 0 regardless of firm toggle.
# ---------------------------------------------------------------------------

class TestEnvKillSwitchOff:

    def test_env_kill_switch_blocks_all_firms(self, monkeypatch):
        """When NURTURE_SENDS_ENABLED is false, the tick exits immediately."""
        firm = _make_firm(nurture_enabled=True)
        lead = _make_lead(firm.id)
        seq_id, ver_id, step_id = _make_sequence_with_email_step(firm.id)
        enr = _make_enrollment(
            firm.id, lead.id, seq_id, ver_id, step_id,
            next_action_time=datetime.now(timezone.utc) - timedelta(minutes=5),
        )

        class _NoSends:
            NURTURE_SENDS_ENABLED = False
            FRONTEND_URL = "http://localhost:3000"

        monkeypatch.setattr(
            "app.services.nurture_execution_service.get_settings",
            lambda: _NoSends(),
        )

        send_calls = []
        monkeypatch.setattr(
            "app.services.nurture_execution_service.EmailService.send_nurture_email",
            lambda **kw: send_calls.append(kw),
        )

        result = run_nurture_tick()

        assert result["checked"] == 0, (
            f"Expected 0 checked when env kill switch off, got {result['checked']}"
        )
        assert result["sent"] == 0, f"Expected 0 sent, got {result['sent']}"
        assert len(send_calls) == 0, "send_nurture_email must not be called when env switch off"

        db = TestingSessionLocal()
        try:
            refreshed = db.query(Enrollment).filter(Enrollment.id == enr.id).first()
            assert refreshed.next_action_time == enr.next_action_time, (
                "next_action_time must not change when env kill switch is off"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Guard test 3: resume re-basing via real PATCH /firms/me endpoint
#
# BREAK: Remove the rebase pass from the PATCH /me handler.
# EXPECTED RED: next_action_time remains stale (3 weeks in the past).
# RESTORE: re-add the rebase pass.
# CONFIRM GREEN: next_action_time is within a few seconds of now.
# ---------------------------------------------------------------------------

class TestResumeRebasing:

    def test_rebase_on_toggle_true_via_patch_me(self, client):
        """Flipping toggle to true via PATCH /firms/me rebases stale wait_fixed timers."""
        firm, owner = _make_firm_with_owner(nurture_enabled=False)
        lead = _make_lead(firm.id)
        seq_id, ver_id, step_id = _make_wait_fixed_step(firm.id, duration_seconds=3600)

        stale_time = datetime.now(timezone.utc) - timedelta(weeks=3)
        enr = _make_enrollment(
            firm.id, lead.id, seq_id, ver_id, step_id,
            next_action_time=stale_time,
        )

        login = client.post("/auth/token", json={"username": owner.email, "password": "testpass123"})
        assert login.status_code == 200, f"Login failed: {login.json()}"
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        before_flip = datetime.now(timezone.utc)

        resp = client.patch("/firms/me", json={"nurture_enabled": True}, headers=headers)
        assert resp.status_code == 200, f"PATCH /firms/me failed: {resp.json()}"
        assert resp.json()["nurture_enabled"] is True

        after_flip = datetime.now(timezone.utc)

        db = TestingSessionLocal()
        try:
            refreshed = db.query(Enrollment).filter(Enrollment.id == enr.id).first()
            assert refreshed.next_action_time is not None, "next_action_time must not be None after rebase"
            assert refreshed.next_action_time > stale_time, (
                f"next_action_time {refreshed.next_action_time} must be > stale {stale_time}"
            )
            db.query(Step).filter(Step.id == step_id).first()
            expected_nat = before_flip + timedelta(seconds=3600)
            assert refreshed.next_action_time >= before_flip, (
                f"Rebased time {refreshed.next_action_time} must be >= {before_flip}"
            )
            assert refreshed.next_action_time <= after_flip + timedelta(seconds=3600), (
                f"Rebased time {refreshed.next_action_time} too far in future"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Test 4: firm.nurture_toggled fires on both directions
# ---------------------------------------------------------------------------

class TestNurtureToggledEvent:

    def _flip_via_patch_me(self, client, firm, owner_email, new_value: bool):
        login = client.post("/auth/token", json={"username": owner_email, "password": "testpass123"})
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        resp = client.patch("/firms/me", json={"nurture_enabled": new_value}, headers=headers)
        assert resp.status_code == 200
        return resp

    def test_event_fires_on_false_to_true(self, client):
        """firm.nurture_toggled fires with nurture_enabled=True when toggle flips on."""
        from app.models.behavioral_event import BehavioralEvent

        firm, owner = _make_firm_with_owner(nurture_enabled=False)
        self._flip_via_patch_me(client, firm, owner.email, True)

        db = TestingSessionLocal()
        try:
            event = db.query(BehavioralEvent).filter(
                BehavioralEvent.event_type == "firm.nurture_toggled",
                BehavioralEvent.entity_id == firm.id,
            ).first()
            assert event is not None, "firm.nurture_toggled event must be written"
            assert event.extra_metadata.get("nurture_enabled") is True, (
                f"metadata.nurture_enabled must be True, got {event.metadata}"
            )
        finally:
            db.close()

    def test_event_fires_on_true_to_false(self, client):
        """firm.nurture_toggled fires with nurture_enabled=False when toggle flips off."""
        from app.models.behavioral_event import BehavioralEvent

        firm, owner = _make_firm_with_owner(nurture_enabled=True)
        self._flip_via_patch_me(client, firm, owner.email, False)

        db = TestingSessionLocal()
        try:
            event = db.query(BehavioralEvent).filter(
                BehavioralEvent.event_type == "firm.nurture_toggled",
                BehavioralEvent.entity_id == firm.id,
            ).first()
            assert event is not None, "firm.nurture_toggled event must be written"
            assert event.extra_metadata.get("nurture_enabled") is False, (
                f"metadata.nurture_enabled must be False, got {event.metadata}"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Test 5: toggle-off firm excluded at the query level (not just skipped in tick)
# ---------------------------------------------------------------------------

class TestQueryLevelExclusion:

    def test_toggle_off_firm_excluded_from_get_due_enrollments(self):
        """get_due_enrollments never returns enrollments for a toggle-off firm."""
        firm_off = _make_firm(nurture_enabled=False)
        firm_on = _make_firm(nurture_enabled=True)

        lead_off = _make_lead(firm_off.id)
        lead_on = _make_lead(firm_on.id)

        seq_off_id, ver_off_id, step_off_id = _make_sequence_with_email_step(firm_off.id)
        seq_on_id, ver_on_id, step_on_id = _make_sequence_with_email_step(firm_on.id)

        now = datetime.now(timezone.utc)
        enr_off = _make_enrollment(
            firm_off.id, lead_off.id, seq_off_id, ver_off_id, step_off_id,
            next_action_time=now - timedelta(minutes=1),
        )
        enr_on = _make_enrollment(
            firm_on.id, lead_on.id, seq_on_id, ver_on_id, step_on_id,
            next_action_time=now - timedelta(minutes=1),
        )

        db = TestingSessionLocal()
        try:
            due = get_due_enrollments(db=db, firm_id=None, now=now)
            due_ids = {e.id for e in due}

            assert enr_on.id in due_ids, (
                "Enrollment for toggle-on firm must appear in get_due_enrollments"
            )
            assert enr_off.id not in due_ids, (
                "Enrollment for toggle-off firm must NOT appear in get_due_enrollments"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Test 6: business hours and hold_for_approval still apply when toggle is true
# ---------------------------------------------------------------------------

class TestGuardStillApplyWhenToggleOn:

    def test_business_hours_still_hold_when_toggle_true(self, monkeypatch):
        """A toggle-on firm with a step outside business hours is held, not sent."""
        firm = _make_firm(nurture_enabled=True)
        firm_tz = "UTC"
        db = TestingSessionLocal()
        try:
            f = db.query(Firm).filter(Firm.id == firm.id).first()
            f.business_hours_start = 9
            f.business_hours_end = 17
            f.timezone = firm_tz
            db.commit()
        finally:
            db.close()

        lead = _make_lead(firm.id)
        seq_id, ver_id, step_id = _make_sequence_with_email_step(firm.id)

        utc_3am = datetime(2026, 9, 4, 3, 0, 0, tzinfo=timezone.utc)

        class _FixedDatetime:
            @staticmethod
            def now(tz=None):
                return utc_3am

        monkeypatch.setattr("app.services.nurture_execution_service.datetime", _FixedDatetime)

        enr = _make_enrollment(
            firm.id, lead.id, seq_id, ver_id, step_id,
            next_action_time=utc_3am - timedelta(minutes=5),
        )

        send_calls = []
        monkeypatch.setattr(
            "app.services.nurture_execution_service.EmailService.send_nurture_email",
            lambda **kw: send_calls.append(kw),
        )

        result = run_nurture_tick()

        assert result["held_for_business_hours"] >= 1, (
            f"Expected held_for_business_hours >= 1, got {result}"
        )
        assert len(send_calls) == 0, "No email must be sent outside business hours"

    def test_hold_for_approval_still_applies_when_toggle_true(self, monkeypatch):
        """A hold_for_approval action step is held (not sent) even when toggle is true."""
        firm = _make_firm(nurture_enabled=True)
        lead = _make_lead(firm.id)

        db = TestingSessionLocal()
        try:
            seq = Sequence(firm_id=firm.id, name="Hold Approval Seq")
            db.add(seq)
            db.flush()
            ver = SequenceVersion(sequence_id=seq.id, version_number=1)
            db.add(ver)
            db.flush()
            step = Step(
                sequence_version_id=ver.id,
                step_key="hold1",
                step_type=StepType.action.value,
                channel="email",
                config={"hold_for_approval": True},
            )
            db.add(step)
            db.commit()
            seq_id, ver_id, step_id = seq.id, ver.id, step.id
            enr = Enrollment(
                firm_id=firm.id,
                lead_id=lead.id,
                sequence_id=seq_id,
                sequence_version_id=ver_id,
                current_step_id=step_id,
                next_action_time=datetime.now(timezone.utc) - timedelta(minutes=1),
                status=EnrollmentStatus.active.value,
                loop_counts={},
            )
            db.add(enr)
            db.commit()
            enr_id = enr.id
        finally:
            db.close()

        send_calls = []
        monkeypatch.setattr(
            "app.services.nurture_execution_service.EmailService.send_nurture_email",
            lambda **kw: send_calls.append(kw),
        )

        result = run_nurture_tick()

        assert result["held_for_approval"] >= 1, (
            f"Expected held_for_approval >= 1, got {result}"
        )
        assert len(send_calls) == 0, "No email must fire from a hold_for_approval step"

        db = TestingSessionLocal()
        try:
            refreshed = db.query(Enrollment).filter(Enrollment.id == enr_id).first()
            assert refreshed.status == EnrollmentStatus.held_for_approval.value, (
                f"Enrollment must be held_for_approval, got {refreshed.status}"
            )
        finally:
            db.close()
