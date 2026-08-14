# tests/test_nurture_execution.py
"""
Tests for the nurture engine tick loop (app/services/nurture_execution_service.py).

GUARD TEST: test_enrollment_advances_even_when_send_raises
Proves the write-then-send guarantee: advance_enrollment() is called before
EmailService.send_nurture_email(), so a send failure never un-advances an
enrollment. See the watched-fail cycle documentation in the class docstring.
"""

import uuid
from datetime import datetime, timezone, timedelta

import pytest

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.lead import Lead
from app.models.sequence import Sequence, SequenceVersion, Step, StepEdge
from app.models.enrollment import Enrollment
from app.models.suppressed_email import SuppressedEmail
from app.core.enums import LeadProvenance, EnrollmentStatus, StepType
from app.crud.enrollment import get_due_enrollments
from app.services.nurture_execution_service import run_nurture_tick


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_firm(slug: str) -> Firm:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Nurture Test Firm {slug}", slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)
        _ = firm.id, firm.name
        return firm
    finally:
        db.close()


def _make_lead(firm_id, email: str = None) -> Lead:
    db = TestingSessionLocal()
    try:
        lead = Lead(
            firm_id=firm_id,
            name="Nurture Test Lead",
            email=email or f"nurture-{uuid.uuid4()}@example.com",
            provenance=LeadProvenance.firm_entered.value,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        _ = lead.id, lead.firm_id, lead.email
        return lead
    finally:
        db.close()


def _make_sequence_and_version(firm_id):
    """Create a Sequence and one SequenceVersion. Returns (sequence, version)."""
    db = TestingSessionLocal()
    try:
        sequence = Sequence(firm_id=firm_id, name="Nurture Test Sequence")
        db.add(sequence)
        db.flush()
        version = SequenceVersion(sequence_id=sequence.id, version_number=1)
        db.add(version)
        db.commit()
        db.refresh(sequence)
        db.refresh(version)
        _ = sequence.id, version.id
        return sequence, version
    finally:
        db.close()


def _make_step(version_id, step_key: str, config: dict = None) -> Step:
    """Create an email-type Step."""
    db = TestingSessionLocal()
    try:
        step = Step(
            sequence_version_id=version_id,
            step_key=step_key,
            step_type=StepType.email.value,
            channel="email",
            config=config or {"subject": "Test Subject", "body": "<p>Test body</p>"},
        )
        db.add(step)
        db.commit()
        db.refresh(step)
        _ = step.id, step.step_key
        return step
    finally:
        db.close()


def _make_edge(from_step_id, to_step_id) -> StepEdge:
    db = TestingSessionLocal()
    try:
        edge = StepEdge(from_step_id=from_step_id, to_step_id=to_step_id)
        db.add(edge)
        db.commit()
        db.refresh(edge)
        _ = edge.id
        return edge
    finally:
        db.close()


def _make_enrollment(
    firm_id,
    lead_id,
    sequence_id,
    sequence_version_id,
    current_step_id=None,
    next_action_time=None,
) -> Enrollment:
    db = TestingSessionLocal()
    try:
        enrollment = Enrollment(
            firm_id=firm_id,
            lead_id=lead_id,
            sequence_id=sequence_id,
            sequence_version_id=sequence_version_id,
            current_step_id=current_step_id,
            next_action_time=next_action_time,
        )
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)
        _ = enrollment.id, enrollment.status
        return enrollment
    finally:
        db.close()


def _fetch_enrollment(enrollment_id):
    """Re-fetch enrollment from DB to get current committed state."""
    db = TestingSessionLocal()
    try:
        row = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
        if row is None:
            return None
        _ = row.current_step_id, row.next_action_time, row.status
        return row
    finally:
        db.close()


def _add_suppression(firm_id, email: str):
    db = TestingSessionLocal()
    try:
        row = SuppressedEmail(
            firm_id=firm_id,
            email=email.lower().strip(),
            reason="test",
            suppressed_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GUARD TEST: write-then-send guarantee
#
# This test proves advance_enrollment() is called BEFORE send_nurture_email().
# The watched-fail cycle for this test:
#
#   BREAK: In run_nurture_tick(), swap step 8 and step 9 so send_nurture_email
#          is called BEFORE advance_enrollment().
#   RUN:   pytest tests/test_nurture_execution.py::TestWriteThenSendGuarantee::test_enrollment_advances_even_when_send_raises -v
#   EXPECT RED: AssertionError -- enrollment.current_step_id is still step1.id
#               (the send raised before advance could run, so nothing advanced)
#   RESTORE: git checkout app/services/nurture_execution_service.py
#   RERUN:  confirm GREEN -- enrollment.current_step_id == step2.id even though
#           send raised, because advance happened first.
# ---------------------------------------------------------------------------

class TestWriteThenSendGuarantee:
    def test_enrollment_advances_even_when_send_raises(self, monkeypatch):
        """Enrollment advances to the next step even when send_nurture_email raises.

        The send is wrapped in try/except inside run_nurture_tick, so a Postmark
        failure never blocks the advance. The advance must have already committed
        before the send is attempted (write-then-send order).
        """
        firm = _make_firm(f"guard-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        sequence, version = _make_sequence_and_version(firm.id)
        step1 = _make_step(version.id, "S1")
        step2 = _make_step(version.id, "S2")
        _make_edge(step1.id, step2.id)

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        enrollment = _make_enrollment(
            firm_id=firm.id,
            lead_id=lead.id,
            sequence_id=sequence.id,
            sequence_version_id=version.id,
            current_step_id=step1.id,
            next_action_time=past,
        )

        from app.services import email_service as email_mod

        def _raise(*args, **kwargs):
            raise RuntimeError("simulated Postmark failure")

        monkeypatch.setattr(email_mod.EmailService, "send_nurture_email", staticmethod(_raise))

        result = run_nurture_tick()

        assert result["checked"] == 1
        assert result["failed_sends"] == 1
        assert result["sent"] == 0

        fetched = _fetch_enrollment(enrollment.id)
        assert fetched.current_step_id == step2.id, (
            f"Write-then-send guarantee violated: enrollment was NOT advanced despite "
            f"send raising. current_step_id={fetched.current_step_id}, expected {step2.id}. "
            f"This means advance_enrollment() ran AFTER send_nurture_email(), which is wrong."
        )
        assert fetched.next_action_time is None


# ---------------------------------------------------------------------------
# Suppressed lead is skipped
# ---------------------------------------------------------------------------

class TestSuppressionSkip:
    def test_suppressed_lead_is_not_sent_to(self, monkeypatch):
        """An enrollment whose lead email is suppressed is stopped, not sent to."""
        firm = _make_firm(f"suppressed-{uuid.uuid4().hex[:6]}")
        lead_email = f"suppressed-{uuid.uuid4()}@example.com"
        lead = _make_lead(firm.id, email=lead_email)
        sequence, version = _make_sequence_and_version(firm.id)
        step1 = _make_step(version.id, "S1")
        step2 = _make_step(version.id, "S2")
        _make_edge(step1.id, step2.id)

        _add_suppression(firm.id, lead_email)

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        enrollment = _make_enrollment(
            firm_id=firm.id,
            lead_id=lead.id,
            sequence_id=sequence.id,
            sequence_version_id=version.id,
            current_step_id=step1.id,
            next_action_time=past,
        )

        send_calls = []

        def _record_send(*args, **kwargs):
            send_calls.append((args, kwargs))

        from app.services import email_service as email_mod
        monkeypatch.setattr(
            email_mod.EmailService, "send_nurture_email", staticmethod(_record_send)
        )

        result = run_nurture_tick()

        assert result["suppressed"] == 1
        assert result["sent"] == 0
        assert send_calls == [], "send_nurture_email must not be called for suppressed leads"

        fetched = _fetch_enrollment(enrollment.id)
        assert fetched.status == EnrollmentStatus.unsubscribed.value, (
            f"Expected enrollment status=unsubscribed after suppression, got {fetched.status}"
        )
        assert fetched.current_step_id == step1.id, (
            "Suppressed enrollment must not advance its current_step_id"
        )


# ---------------------------------------------------------------------------
# get_due_enrollments timing precision
# ---------------------------------------------------------------------------

class TestDueEnrollmentsTiming:
    def test_past_enrollment_is_returned_future_is_not(self):
        """get_due_enrollments returns past/present next_action_time, not future."""
        firm = _make_firm(f"timing-{uuid.uuid4().hex[:6]}")
        lead_past = _make_lead(firm.id)
        lead_future = _make_lead(firm.id)
        sequence, version = _make_sequence_and_version(firm.id)
        step = _make_step(version.id, "S1")

        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=5)
        future = now + timedelta(hours=1)

        enr_past = _make_enrollment(
            firm_id=firm.id,
            lead_id=lead_past.id,
            sequence_id=sequence.id,
            sequence_version_id=version.id,
            current_step_id=step.id,
            next_action_time=past,
        )
        enr_future = _make_enrollment(
            firm_id=firm.id,
            lead_id=lead_future.id,
            sequence_id=sequence.id,
            sequence_version_id=version.id,
            current_step_id=step.id,
            next_action_time=future,
        )

        db = TestingSessionLocal()
        try:
            due = get_due_enrollments(db=db, firm_id=None, now=now)
            due_ids = {e.id for e in due}
        finally:
            db.close()

        assert enr_past.id in due_ids, (
            f"Past enrollment (next_action_time={past}) was not returned as due"
        )
        assert enr_future.id not in due_ids, (
            f"Future enrollment (next_action_time={future}) should not be due yet"
        )

    def test_null_next_action_time_is_never_due(self):
        """Enrollments with next_action_time=None are never returned as due."""
        firm = _make_firm(f"null-nat-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        sequence, version = _make_sequence_and_version(firm.id)
        step = _make_step(version.id, "S1")

        enr = _make_enrollment(
            firm_id=firm.id,
            lead_id=lead.id,
            sequence_id=sequence.id,
            sequence_version_id=version.id,
            current_step_id=step.id,
            next_action_time=None,
        )

        db = TestingSessionLocal()
        try:
            due = get_due_enrollments(
                db=db, firm_id=None, now=datetime.now(timezone.utc)
            )
            due_ids = {e.id for e in due}
        finally:
            db.close()

        assert enr.id not in due_ids, (
            "Enrollment with next_action_time=None must never appear as due"
        )


# ---------------------------------------------------------------------------
# Tenant isolation for get_due_enrollments
# ---------------------------------------------------------------------------

class TestDueEnrollmentsTenantIsolation:
    def test_firm_id_filter_scopes_to_correct_firm(self):
        """get_due_enrollments with a firm_id never returns another firm's enrollments."""
        firm_a = _make_firm(f"iso-a-{uuid.uuid4().hex[:6]}")
        firm_b = _make_firm(f"iso-b-{uuid.uuid4().hex[:6]}")

        lead_a = _make_lead(firm_a.id)
        lead_b = _make_lead(firm_b.id)

        seq_a, ver_a = _make_sequence_and_version(firm_a.id)
        seq_b, ver_b = _make_sequence_and_version(firm_b.id)

        step_a = _make_step(ver_a.id, "S1")
        step_b = _make_step(ver_b.id, "S1")

        past = datetime.now(timezone.utc) - timedelta(hours=1)

        enr_a = _make_enrollment(
            firm_id=firm_a.id,
            lead_id=lead_a.id,
            sequence_id=seq_a.id,
            sequence_version_id=ver_a.id,
            current_step_id=step_a.id,
            next_action_time=past,
        )
        enr_b = _make_enrollment(
            firm_id=firm_b.id,
            lead_id=lead_b.id,
            sequence_id=seq_b.id,
            sequence_version_id=ver_b.id,
            current_step_id=step_b.id,
            next_action_time=past,
        )

        db = TestingSessionLocal()
        try:
            due_a = get_due_enrollments(
                db=db, firm_id=firm_a.id, now=datetime.now(timezone.utc)
            )
            due_a_ids = {e.id for e in due_a}

            due_b = get_due_enrollments(
                db=db, firm_id=firm_b.id, now=datetime.now(timezone.utc)
            )
            due_b_ids = {e.id for e in due_b}
        finally:
            db.close()

        assert enr_a.id in due_a_ids, "Firm A enrollment must appear in Firm A's due list"
        assert enr_b.id not in due_a_ids, (
            "Tenant isolation breach: Firm B enrollment appeared in Firm A's due list"
        )

        assert enr_b.id in due_b_ids, "Firm B enrollment must appear in Firm B's due list"
        assert enr_a.id not in due_b_ids, (
            "Tenant isolation breach: Firm A enrollment appeared in Firm B's due list"
        )
