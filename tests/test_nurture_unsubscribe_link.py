# tests/test_nurture_unsubscribe_link.py
"""
Tests for the unsubscribe token generation and injection in run_nurture_tick().

Covers:
  1. An email step processed by run_nurture_tick() produces a real, non-null
     unsubscribe_token_hash and unsubscribe_token_expires_at on the Enrollment row.
  2. End-to-end roundtrip: the raw token that would be in the email link, when
     passed to verify_and_process_unsubscribe(), succeeds and adds the lead to
     the suppression list -- proving the generate and verify halves connect.
  3. A suppressed lead's enrollment does NOT get a new unsubscribe token because
     the suppression check short-circuits before the token generation code runs.
  4. The token write is in the same advance_enrollment() call as the step advance
     (same DB commit) -- not a separate transaction that could crash between them.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import TestingSessionLocal
from app.core.enums import EnrollmentStatus, LeadProvenance, StepType
from app.core.security import get_password_hash
from app.models.enrollment import Enrollment
from app.models.firm import Firm
from app.models.lead import Lead
from app.models.lead_message import LeadMessage
from app.models.sequence import Sequence, SequenceVersion, Step, StepEdge
from app.models.suppressed_email import SuppressedEmail
from app.services.nurture_execution_service import run_nurture_tick
from app.services.unsubscribe_service import verify_and_process_unsubscribe


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


def _make_lead(firm_id, email: str = None) -> Lead:
    db = TestingSessionLocal()
    try:
        lead = Lead(
            firm_id=firm_id,
            name="Test Lead",
            email=email or f"lead-{uuid.uuid4().hex[:8]}@example.com",
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


def _make_email_sequence(firm_id) -> tuple:
    """Create a minimal sequence with one email step followed by a done step."""
    db = TestingSessionLocal()
    try:
        now = datetime.now(timezone.utc)
        seq = Sequence(firm_id=firm_id, name="Test Seq", is_active=True, created_at=now, updated_at=now)
        db.add(seq)
        db.flush()
        ver = SequenceVersion(
            sequence_id=seq.id, version_number=1,
            preset_lineage_key="test_unsub", created_at=now,
        )
        db.add(ver)
        db.flush()
        email_step = Step(
            sequence_version_id=ver.id,
            step_key="E1",
            step_type=StepType.email,
            channel="email",
            config={"subject": "Test Subject", "body": "Hello {{name}}."},
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
        edge = StepEdge(
            from_step_id=email_step.id,
            to_step_id=done_step.id,
            created_at=now,
        )
        db.add(edge)
        seq.current_version_id = ver.id
        db.commit()
        ver_id = ver.id
        email_step_id = email_step.id
    finally:
        db.close()
    return ver_id, email_step_id


def _make_enrollment(firm_id, lead_id, version_id, seq_id, step_id=None) -> Enrollment:
    db = TestingSessionLocal()
    try:
        now = datetime.now(timezone.utc)
        e = Enrollment(
            firm_id=firm_id,
            lead_id=lead_id,
            sequence_id=seq_id,
            sequence_version_id=version_id,
            current_step_id=step_id,
            next_action_time=now - timedelta(seconds=1),
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


def _get_seq_id_from_ver(ver_id) -> uuid.UUID:
    db = TestingSessionLocal()
    try:
        ver = db.query(SequenceVersion).filter(SequenceVersion.id == ver_id).first()
        return ver.sequence_id
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1. Token written after email tick
# ---------------------------------------------------------------------------

class TestUnsubscribeTokenWritten:

    def test_email_tick_writes_token_hash_and_expiry(self, monkeypatch):
        """After run_nurture_tick() processes an email step, the Enrollment has a real token hash and expiry."""
        monkeypatch.setattr(
            "app.services.nurture_execution_service.EmailService.send_nurture_email",
            lambda **kw: None,
        )

        firm = _make_firm(f"ut1-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        ver_id, email_step_id = _make_email_sequence(firm.id)
        seq_id = _get_seq_id_from_ver(ver_id)
        enrollment = _make_enrollment(firm.id, lead.id, ver_id, seq_id, step_id=email_step_id)

        run_nurture_tick()

        db = TestingSessionLocal()
        try:
            refreshed = db.query(Enrollment).filter(Enrollment.id == enrollment.id).first()
            assert refreshed.unsubscribe_token_hash is not None, (
                "unsubscribe_token_hash must be set after an email step is sent"
            )
            assert refreshed.unsubscribe_token_expires_at is not None, (
                "unsubscribe_token_expires_at must be set after an email step is sent"
            )
            # Expiry should be roughly 10 years in the future
            days_remaining = (refreshed.unsubscribe_token_expires_at - datetime.now(timezone.utc)).days
            assert days_remaining > 3600, (
                f"Expected ~3650 days expiry, got {days_remaining} days"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 2. End-to-end roundtrip: generate -> verify
# ---------------------------------------------------------------------------

class TestUnsubscribeRoundtrip:

    def test_generated_token_verifies_and_suppresses(self, monkeypatch):
        """End-to-end: the token generated during a tick can be used to actually unsubscribe.

        Captures the raw_token passed through by intercepting the email body URL,
        then verifies it successfully processes the unsubscribe.
        """
        captured_bodies = []

        def capture_send(**kw):
            captured_bodies.append(kw.get("html_body", ""))

        monkeypatch.setattr(
            "app.services.nurture_execution_service.EmailService.send_nurture_email",
            capture_send,
        )

        firm = _make_firm(f"ut2-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        ver_id, email_step_id = _make_email_sequence(firm.id)
        seq_id = _get_seq_id_from_ver(ver_id)
        enrollment = _make_enrollment(firm.id, lead.id, ver_id, seq_id, step_id=email_step_id)

        run_nurture_tick()

        assert len(captured_bodies) == 1, "Expected exactly one email to be sent"
        body = captured_bodies[0]

        # Extract the raw token from the body's unsubscribe URL.
        # The URL pattern is /unsubscribe/{raw_token} in the body.
        import re
        match = re.search(r'/unsubscribe/([a-f0-9]{64})', body)
        assert match is not None, f"Could not find /unsubscribe/<token> in body: {body[:200]!r}"
        raw_token = match.group(1)

        # Verify the raw token matches the hash stored on the enrollment.
        expected_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        db = TestingSessionLocal()
        try:
            refreshed = db.query(Enrollment).filter(Enrollment.id == enrollment.id).first()
            assert refreshed.unsubscribe_token_hash == expected_hash, (
                "Hash in DB does not match hash of token found in email body -- "
                "the two halves are not connected"
            )
        finally:
            db.close()

        # Now actually call verify_and_process_unsubscribe with the real raw token.
        db2 = TestingSessionLocal()
        try:
            result = verify_and_process_unsubscribe(db=db2, raw_token=raw_token)
            assert result is True, "verify_and_process_unsubscribe returned False for a valid token"

            # Confirm the lead is now on the suppression list.
            suppressed = (
                db2.query(SuppressedEmail)
                .filter(
                    SuppressedEmail.firm_id == firm.id,
                    SuppressedEmail.email == lead.email,
                )
                .first()
            )
            assert suppressed is not None, "Lead email not added to suppression list after unsubscribe"
        finally:
            db2.close()


# ---------------------------------------------------------------------------
# 3. Suppressed lead: no token generated
# ---------------------------------------------------------------------------

class TestSuppressedLeadNoToken:

    def test_suppressed_lead_does_not_get_token(self, monkeypatch):
        """A suppressed lead's enrollment is stopped before any token is generated."""
        monkeypatch.setattr(
            "app.services.nurture_execution_service.EmailService.send_nurture_email",
            lambda **kw: None,
        )

        firm = _make_firm(f"ut3-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        # Add the lead to the suppression list BEFORE the tick.
        db = TestingSessionLocal()
        try:
            sup = SuppressedEmail(
                firm_id=firm.id,
                email=lead.email,
                reason="unsubscribed",
            )
            db.add(sup)
            db.commit()
        finally:
            db.close()

        ver_id, email_step_id = _make_email_sequence(firm.id)
        seq_id = _get_seq_id_from_ver(ver_id)
        enrollment = _make_enrollment(firm.id, lead.id, ver_id, seq_id, step_id=email_step_id)

        run_nurture_tick()

        db = TestingSessionLocal()
        try:
            refreshed = db.query(Enrollment).filter(Enrollment.id == enrollment.id).first()
            # Suppressed enrollment should be stopped, not advanced to email step.
            assert refreshed.status == EnrollmentStatus.unsubscribed.value, (
                f"Expected suppressed enrollment to have status unsubscribed, got {refreshed.status}"
            )
            # No unsubscribe token should have been generated.
            assert refreshed.unsubscribe_token_hash is None, (
                "unsubscribe_token_hash must NOT be set for a suppressed lead -- "
                "the suppression check should short-circuit before token generation"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 4. Token write is in the same advance_enrollment commit as the step advance
# ---------------------------------------------------------------------------

class TestWriteOrdering:

    def test_token_write_is_atomic_with_step_advance(self, monkeypatch):
        """The token hash is written in the same advance_enrollment call as the step advance.

        Proof: we intercept advance_enrollment itself and capture its keyword
        arguments. If new_unsubscribe_token_hash is passed to the same call
        as new_current_step_id, they are in the same DB transaction.
        """
        advance_calls = []

        original_advance = __import__(
            'app.crud.enrollment', fromlist=['advance_enrollment']
        ).advance_enrollment

        def capturing_advance(**kwargs):
            advance_calls.append(dict(kwargs))
            return original_advance(**kwargs)

        monkeypatch.setattr(
            "app.services.nurture_execution_service.crud_enrollment.advance_enrollment",
            capturing_advance,
        )
        monkeypatch.setattr(
            "app.services.nurture_execution_service.EmailService.send_nurture_email",
            lambda **kw: None,
        )

        firm = _make_firm(f"ut4-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        ver_id, email_step_id = _make_email_sequence(firm.id)
        seq_id = _get_seq_id_from_ver(ver_id)
        _make_enrollment(firm.id, lead.id, ver_id, seq_id, step_id=email_step_id)

        run_nurture_tick()

        # Find the advance call that actually moved the email step forward.
        email_step_advances = [
            c for c in advance_calls
            if c.get("new_unsubscribe_token_hash") is not None
        ]
        assert len(email_step_advances) == 1, (
            f"Expected exactly one advance_enrollment call carrying a token hash, "
            f"got {len(email_step_advances)}. All calls: {advance_calls}"
        )
        call = email_step_advances[0]
        # Both the step advance and the token are in the same call.
        assert "new_current_step_id" in call, "new_current_step_id must be in the same call"
        assert "new_unsubscribe_token_hash" in call, "token hash must be in the same call"
        assert "new_unsubscribe_token_expires_at" in call, "token expiry must be in the same call"
