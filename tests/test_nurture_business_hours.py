# tests/test_nurture_business_hours.py
"""
Tests for the business-hours send window in run_nurture_tick().

Contract section 6.1 requires nurture sends to respect firm business hours
(default 8am-6pm firm-local). These tests verify:

  1. A due email step outside business hours is HELD: no email sent, enrollment
     next_action_time pushed forward 30 minutes, current_step_id unchanged.
  2. The same due email step inside business hours sends normally -- regression
     guard confirming the existing send path is unaffected when hours are open.
  3. A step with bypass_business_hours: true sends even outside business hours.
     (Watched-fail verified: see docstring on the test class.)
  4. Firm.business_hours_start / business_hours_end default to 8 and 18 for a
     firm created without explicit values.
  5. Timezone localization: a firm on America/Los_Angeles with default hours,
     tested at UTC times that are 7am Pacific (hold) and 9am Pacific (send).
"""

import uuid
import datetime as dt_module
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from tests.conftest import TestingSessionLocal
from app.core.enums import EnrollmentStatus, LeadProvenance, StepType
from app.models.enrollment import Enrollment
from app.models.firm import Firm
from app.models.lead import Lead
from app.models.sequence import Sequence, SequenceVersion, Step, StepEdge
from app.services.nurture_execution_service import run_nurture_tick


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm(slug: str, tz: str = "UTC", bh_start: int = 8, bh_end: int = 18) -> Firm:
    db = TestingSessionLocal()
    try:
        firm = Firm(
            name=f"Firm {slug}",
            slug=slug,
            timezone=tz,
            business_hours_start=bh_start,
            business_hours_end=bh_end,
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
            name="Test Lead",
            email=f"lead-{uuid.uuid4().hex[:8]}@example.com",
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


def _make_email_sequence(firm_id, step_config: dict = None) -> tuple:
    """One email step + one done step. Returns (version_id, seq_id, email_step_id)."""
    db = TestingSessionLocal()
    try:
        now = datetime.now(timezone.utc)
        seq = Sequence(
            firm_id=firm_id, name="BH Test Seq", is_active=True,
            created_at=now, updated_at=now,
        )
        db.add(seq)
        db.flush()
        ver = SequenceVersion(
            sequence_id=seq.id, version_number=1,
            preset_lineage_key=f"bh-test-{uuid.uuid4().hex[:6]}", created_at=now,
        )
        db.add(ver)
        db.flush()
        email_step = Step(
            sequence_version_id=ver.id,
            step_key="E1",
            step_type=StepType.email,
            channel="email",
            config=step_config or {"subject": "Hello", "body": "Body text."},
            created_at=now,
        )
        done_step = Step(
            sequence_version_id=ver.id,
            step_key="DONE",
            step_type=StepType.action,
            channel="email",
            config={},
            created_at=now,
        )
        db.add(email_step)
        db.add(done_step)
        db.flush()
        db.add(StepEdge(from_step_id=email_step.id, to_step_id=done_step.id, created_at=now))
        seq.current_version_id = ver.id
        db.commit()
        ver_id = ver.id
        seq_id = seq.id
        email_step_id = email_step.id
    finally:
        db.close()
    return ver_id, seq_id, email_step_id


_FAR_PAST = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_enrollment(firm_id, lead_id, version_id, seq_id, step_id,
                     next_action_time: datetime = None) -> Enrollment:
    """Create an active enrollment.

    next_action_time defaults to a far-past timestamp so the enrollment is
    always due regardless of what time the tick runs at (real or mocked).
    Tests that mock time must pass next_action_time=_FAR_PAST (or any time
    before the mocked 'now') -- never rely on datetime.now() here because
    the tick may be frozen at a past UTC hour for business-hours testing.
    """
    db = TestingSessionLocal()
    try:
        now = datetime.now(timezone.utc)
        e = Enrollment(
            firm_id=firm_id,
            lead_id=lead_id,
            sequence_id=seq_id,
            sequence_version_id=version_id,
            current_step_id=step_id,
            next_action_time=next_action_time if next_action_time is not None else _FAR_PAST,
            status=EnrollmentStatus.active,
            enrolled_at=now,
            loop_counts={},
        )
        db.add(e)
        db.commit()
        db.refresh(e)
        _ = e.id
        return e
    finally:
        db.close()


def _make_fixed_datetime_class(fixed_utc: datetime):
    """Return a datetime subclass whose .now() returns fixed_utc."""
    class FixedDatetime(dt_module.datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is not None:
                return fixed_utc.astimezone(tz)
            return fixed_utc
    return FixedDatetime


# ---------------------------------------------------------------------------
# 1. Outside business hours -- email is HELD
# ---------------------------------------------------------------------------

class TestHeldOutsideBusinessHours:

    def test_due_email_outside_hours_is_not_sent(self, monkeypatch):
        """A due email step outside business hours must not send.

        Firm is on UTC with hours 8-18. We freeze time at 03:00 UTC (hour=3),
        which is before the window. The email must not send; next_action_time
        must advance ~30 minutes; current_step_id must remain unchanged.
        """
        # 03:00 UTC is outside 08:00-18:00
        outside_utc = datetime(2026, 8, 20, 3, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(
            "app.services.nurture_execution_service.datetime",
            _make_fixed_datetime_class(outside_utc),
        )

        send_calls = []
        monkeypatch.setattr(
            "app.services.nurture_execution_service.EmailService.send_nurture_email",
            lambda **kw: send_calls.append(kw),
        )

        firm = _make_firm(f"bh1-{uuid.uuid4().hex[:6]}", tz="UTC", bh_start=8, bh_end=18)
        lead = _make_lead(firm.id)
        ver_id, seq_id, step_id = _make_email_sequence(firm.id)
        enrollment = _make_enrollment(firm.id, lead.id, ver_id, seq_id, step_id)

        result = run_nurture_tick()

        assert len(send_calls) == 0, "send_nurture_email must not be called when outside business hours"
        assert result["held_for_business_hours"] == 1

        db = TestingSessionLocal()
        try:
            refreshed = db.query(Enrollment).filter(Enrollment.id == enrollment.id).first()
            assert refreshed.current_step_id == step_id, (
                "current_step_id must not change when holding for business hours"
            )
            retry_delta = refreshed.next_action_time - outside_utc
            assert 25 * 60 <= retry_delta.total_seconds() <= 35 * 60, (
                f"Expected next_action_time ~30 min ahead, got {retry_delta.total_seconds()}s"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 2. Inside business hours -- email sends normally (regression guard)
# ---------------------------------------------------------------------------

class TestSendsInsideBusinessHours:

    def test_due_email_inside_hours_sends_normally(self, monkeypatch):
        """A due email step inside business hours must send exactly as before.

        This is a regression guard: confirms the existing send path (token
        generation, write-then-send ordering) is unaffected when hours are open.
        """
        # 10:00 UTC is inside 08:00-18:00
        inside_utc = datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(
            "app.services.nurture_execution_service.datetime",
            _make_fixed_datetime_class(inside_utc),
        )

        send_calls = []
        monkeypatch.setattr(
            "app.services.nurture_execution_service.EmailService.send_nurture_email",
            lambda **kw: send_calls.append(kw),
        )

        firm = _make_firm(f"bh2-{uuid.uuid4().hex[:6]}", tz="UTC", bh_start=8, bh_end=18)
        lead = _make_lead(firm.id)
        ver_id, seq_id, step_id = _make_email_sequence(firm.id)
        enrollment = _make_enrollment(firm.id, lead.id, ver_id, seq_id, step_id)

        result = run_nurture_tick()

        assert len(send_calls) == 1, "send_nurture_email must be called exactly once when inside business hours"
        assert result["sent"] == 1
        assert result["held_for_business_hours"] == 0

        db = TestingSessionLocal()
        try:
            refreshed = db.query(Enrollment).filter(Enrollment.id == enrollment.id).first()
            assert refreshed.current_step_id != step_id, (
                "Enrollment must have advanced past the email step"
            )
            assert refreshed.unsubscribe_token_hash is not None, (
                "unsubscribe_token_hash must be written on a normal send"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 3. bypass_business_hours: true -- sends even when outside hours
#    WATCHED-FAIL VERIFIED: see class docstring for the negative control.
# ---------------------------------------------------------------------------

class TestBypassBusinessHours:
    """
    Watched-fail verification record:

    To confirm this test genuinely catches the bypass behavior, the bypass
    check in nurture_execution_service.py was temporarily broken by making
    it always return False (i.e., treating bypass=False even when the flag
    is set). With that change in place, the test below went RED with:

        AssertionError: send_nurture_email must be called exactly once for a bypass step
        assert 0 == 1

    The change was then reverted. The test went GREEN again. This confirms
    the test is actually watching the bypass flag, not just passing vacuously.
    """

    def test_bypass_flag_sends_outside_business_hours(self, monkeypatch):
        """A step with bypass_business_hours: true must send even outside business hours."""
        # 03:00 UTC -- outside the default 8-18 window
        outside_utc = datetime(2026, 8, 20, 3, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(
            "app.services.nurture_execution_service.datetime",
            _make_fixed_datetime_class(outside_utc),
        )

        send_calls = []
        monkeypatch.setattr(
            "app.services.nurture_execution_service.EmailService.send_nurture_email",
            lambda **kw: send_calls.append(kw),
        )

        firm = _make_firm(f"bh3-{uuid.uuid4().hex[:6]}", tz="UTC", bh_start=8, bh_end=18)
        lead = _make_lead(firm.id)
        bypass_config = {
            "subject": "Urgent",
            "body": "This sends any time.",
            "bypass_business_hours": True,
        }
        ver_id, seq_id, step_id = _make_email_sequence(firm.id, step_config=bypass_config)
        _make_enrollment(firm.id, lead.id, ver_id, seq_id, step_id)

        result = run_nurture_tick()

        assert len(send_calls) == 1, (
            "send_nurture_email must be called exactly once for a bypass step, "
            "even when outside business hours"
        )
        assert result["sent"] == 1
        assert result["held_for_business_hours"] == 0


# ---------------------------------------------------------------------------
# 4. Default values: business_hours_start=8, business_hours_end=18
# ---------------------------------------------------------------------------

class TestBusinessHoursDefaults:

    def test_firm_defaults_to_8_and_18(self):
        """A firm created without explicit business_hours values gets 8 and 18."""
        db = TestingSessionLocal()
        try:
            firm = Firm(
                name="Defaults Test Firm",
                slug=f"defaults-{uuid.uuid4().hex[:6]}",
                timezone="America/New_York",
            )
            db.add(firm)
            db.commit()
            db.refresh(firm)
            assert firm.business_hours_start == 8, (
                f"Expected business_hours_start=8, got {firm.business_hours_start}"
            )
            assert firm.business_hours_end == 18, (
                f"Expected business_hours_end=18, got {firm.business_hours_end}"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 5. Timezone localization: America/Los_Angeles, 7am Pacific (hold) vs 9am (send)
# ---------------------------------------------------------------------------

class TestTimezoneLocalization:
    """
    Uses real ZoneInfo-based UTC-to-local math. In August 2026, Los Angeles
    is on PDT (UTC-7). The test computes the Pacific hour from the UTC time
    inside the assertion, so if DST rules ever change the assertion adapts
    rather than hardcoding a UTC offset.
    """

    def _run_at_utc(self, monkeypatch, firm, lead, ver_id, seq_id, step_id, utc_time: datetime) -> tuple:
        """Run one tick at a fixed UTC time, return (result, send_call_count)."""
        monkeypatch.setattr(
            "app.services.nurture_execution_service.datetime",
            _make_fixed_datetime_class(utc_time),
        )
        send_calls = []
        monkeypatch.setattr(
            "app.services.nurture_execution_service.EmailService.send_nurture_email",
            lambda **kw: send_calls.append(kw),
        )
        result = run_nurture_tick()
        return result, len(send_calls)

    def test_before_window_la_time_holds(self, monkeypatch):
        """14:00 UTC = 7:00 AM PDT -- before the 8am open, must hold."""
        utc_7am_pacific = datetime(2026, 8, 20, 14, 0, 0, tzinfo=timezone.utc)

        # Verify in the test itself using real ZoneInfo math.
        la_tz = ZoneInfo("America/Los_Angeles")
        local_hour = utc_7am_pacific.astimezone(la_tz).hour
        assert local_hour == 7, (
            f"Test setup error: expected 7am Pacific, got hour={local_hour} "
            f"(DST rules may have changed)"
        )

        firm = _make_firm(f"bh5a-{uuid.uuid4().hex[:6]}", tz="America/Los_Angeles", bh_start=8, bh_end=18)
        lead = _make_lead(firm.id)
        ver_id, seq_id, step_id = _make_email_sequence(firm.id)
        _make_enrollment(firm.id, lead.id, ver_id, seq_id, step_id)

        result, send_count = self._run_at_utc(monkeypatch, firm, lead, ver_id, seq_id, step_id, utc_7am_pacific)

        assert send_count == 0, "Must not send at 7am Pacific -- before 8am open"
        assert result["held_for_business_hours"] == 1

    def test_inside_window_la_time_sends(self, monkeypatch):
        """16:00 UTC = 9:00 AM PDT -- inside the 8am-6pm window, must send."""
        utc_9am_pacific = datetime(2026, 8, 20, 16, 0, 0, tzinfo=timezone.utc)

        la_tz = ZoneInfo("America/Los_Angeles")
        local_hour = utc_9am_pacific.astimezone(la_tz).hour
        assert local_hour == 9, (
            f"Test setup error: expected 9am Pacific, got hour={local_hour} "
            f"(DST rules may have changed)"
        )

        firm = _make_firm(f"bh5b-{uuid.uuid4().hex[:6]}", tz="America/Los_Angeles", bh_start=8, bh_end=18)
        lead = _make_lead(firm.id)
        ver_id, seq_id, step_id = _make_email_sequence(firm.id)
        _make_enrollment(firm.id, lead.id, ver_id, seq_id, step_id)

        result, send_count = self._run_at_utc(monkeypatch, firm, lead, ver_id, seq_id, step_id, utc_9am_pacific)

        assert send_count == 1, "Must send at 9am Pacific -- inside 8am-6pm window"
        assert result["sent"] == 1
        assert result["held_for_business_hours"] == 0
