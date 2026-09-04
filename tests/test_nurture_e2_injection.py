# tests/test_nurture_e2_injection.py
"""
Tests for the E2 answer-button send-flow wiring:
step_key == "5" in run_nurture_tick mints a LeadIntakeToken and injects two
entity_type qualify URLs into the email body before it sends.

Tests:
  1. Due step_key=="5" with merge tags: email body contains two correct qualify
     URLs with a real, valid token.
  2. step_key=="5" body with no merge tags sends unchanged -- no force-append.
  3. step_key=="5" enrollment held for business hours: no token minted.
  4. step_key=="5" enrollment for toggle-off firm: excluded before new code runs.
  5. Other step_key (not "5"): no token minted, body completely unchanged.
  6. End-to-end: URL from injected body hits /qualify/ endpoint, entity_type
     written to Lead, lead.answer_button_clicked event fires.

WATCHED-FAIL PROCEDURE (per How_We_Work_Process_Rules.md section 2):
Break, confirm red, restore, confirm green, confirm git diff matches.
Records are in the commit message.
"""

import re
import uuid
from datetime import datetime, timezone, timedelta

import pytest

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.lead import Lead
from app.models.sequence import Sequence, SequenceVersion, Step, StepEdge
from app.models.enrollment import Enrollment
from app.models.lead_intake_token import LeadIntakeToken
from app.core.enums import LeadProvenance, EnrollmentStatus, StepType
from app.services.nurture_execution_service import run_nurture_tick


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_firm(nurture_enabled: bool = True) -> Firm:
    slug = f"e2-test-{uuid.uuid4().hex[:8]}"
    db = TestingSessionLocal()
    try:
        firm = Firm(
            name=f"E2 Test Firm {slug}",
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


def _make_lead(firm_id) -> Lead:
    db = TestingSessionLocal()
    try:
        lead = Lead(
            firm_id=firm_id,
            name="E2 Test Lead",
            email=f"e2-{uuid.uuid4().hex[:8]}@example.com",
            provenance=LeadProvenance.firm_entered.value,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        _ = lead.id, lead.email
        return lead
    finally:
        db.close()


def _make_email_step(firm_id, step_key: str, body: str) -> tuple:
    """Return (sequence_id, version_id, step_id) for a single email step."""
    db = TestingSessionLocal()
    try:
        seq = Sequence(firm_id=firm_id, name=f"E2 Seq {step_key}")
        db.add(seq)
        db.flush()
        ver = SequenceVersion(sequence_id=seq.id, version_number=1)
        db.add(ver)
        db.flush()
        step = Step(
            sequence_version_id=ver.id,
            step_key=step_key,
            step_type=StepType.email.value,
            channel="email",
            config={"subject": f"E2 Subject {step_key}", "body": body},
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


def _make_enrollment(firm_id, lead_id, sequence_id, version_id, step_id, next_action_time=None) -> Enrollment:
    db = TestingSessionLocal()
    try:
        enr = Enrollment(
            firm_id=firm_id,
            lead_id=lead_id,
            sequence_id=sequence_id,
            sequence_version_id=version_id,
            current_step_id=step_id,
            next_action_time=next_action_time or (datetime.now(timezone.utc) - timedelta(minutes=1)),
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


def _count_tokens_for_lead(lead_id) -> int:
    db = TestingSessionLocal()
    try:
        return db.query(LeadIntakeToken).filter(LeadIntakeToken.lead_id == lead_id).count()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 1: step_key=="5" with merge tags -- body contains two correct qualify URLs
#
# WATCHED-FAIL: Remove the if current_step.step_key == "5": block from
# nurture_execution_service.py. Confirm test goes RED (no URLs in body).
# Restore. Confirm GREEN.
# ---------------------------------------------------------------------------

class TestE2InjectionWithMergeTags:

    def test_body_contains_two_qualify_urls_with_valid_token(self, monkeypatch):
        """
        After the tick, the email body contains two real qualify URLs embedding
        a token that is valid, matches the lead, and contains the correct values.
        """
        body_template = (
            "<p>Hi! Are you filing as:</p>"
            '<a href="{{entity_type_individual_url}}">Individual</a> | '
            '<a href="{{entity_type_business_url}}">Business</a>'
            "{{unsubscribe_url}}"
        )
        firm = _make_firm(nurture_enabled=True)
        lead = _make_lead(firm.id)
        seq_id, ver_id, step_id = _make_email_step(firm.id, "5", body_template)
        _make_enrollment(firm.id, lead.id, seq_id, ver_id, step_id)

        send_calls = []
        monkeypatch.setattr(
            "app.services.nurture_execution_service.EmailService.send_nurture_email",
            lambda **kw: send_calls.append(kw),
        )

        result = run_nurture_tick()

        assert result["sent"] == 1, f"Expected sent=1, got {result}"
        assert len(send_calls) == 1, "Expected exactly one send call"
        html_body = send_calls[0]["html_body"]

        # Both qualify URL patterns must be present
        individual_match = re.search(
            r"/api/backend/intake-token/qualify/([a-f0-9]{64})\?field=entity_type&value=individual",
            html_body,
        )
        business_match = re.search(
            r"/api/backend/intake-token/qualify/([a-f0-9]{64})\?field=entity_type&value=business",
            html_body,
        )
        assert individual_match is not None, (
            f"individual URL not found in body: {html_body[:500]}"
        )
        assert business_match is not None, (
            f"business URL not found in body: {html_body[:500]}"
        )

        # Both URLs embed the same token
        token_individual = individual_match.group(1)
        token_business = business_match.group(1)
        assert token_individual == token_business, (
            "Both qualify URLs must embed the same token"
        )

        # Token is valid and resolves to the correct lead
        from app.services.intake_token_service import validate_intake_token
        db = TestingSessionLocal()
        try:
            result_val = validate_intake_token(db=db, raw_token=token_individual)
        finally:
            db.close()
        assert result_val["status"] == "valid", f"Token must be valid, got {result_val}"
        assert result_val["lead_id"] == str(lead.id), (
            f"Token must resolve to lead {lead.id}, got {result_val['lead_id']}"
        )
        assert result_val["firm_id"] == str(firm.id), (
            f"Token must resolve to firm {firm.id}, got {result_val['firm_id']}"
        )

        # Exactly one token row minted for this lead
        assert _count_tokens_for_lead(lead.id) == 1, "Exactly one token must be minted per send"


# ---------------------------------------------------------------------------
# Test 2: step_key=="5" with no merge tags -- body sends unchanged
# ---------------------------------------------------------------------------

class TestE2NoMergeTags:

    def test_body_without_tags_sends_unchanged(self, monkeypatch):
        """
        A step_key=="5" body with no merge tags sends unchanged. No buttons are
        force-appended. A token is still minted (the send proceeds), but the token
        URL does not appear in the sent body.
        """
        plain_body = "<p>Thanks for your interest! We'll be in touch soon.</p>"
        firm = _make_firm(nurture_enabled=True)
        lead = _make_lead(firm.id)
        seq_id, ver_id, step_id = _make_email_step(firm.id, "5", plain_body)
        _make_enrollment(firm.id, lead.id, seq_id, ver_id, step_id)

        send_calls = []
        monkeypatch.setattr(
            "app.services.nurture_execution_service.EmailService.send_nurture_email",
            lambda **kw: send_calls.append(kw),
        )

        result = run_nurture_tick()

        assert result["sent"] == 1, f"Expected sent=1, got {result}"
        assert len(send_calls) == 1
        html_body = send_calls[0]["html_body"]

        assert "entity_type_individual_url" not in html_body, (
            "Unexpanded merge tag must not appear in sent body"
        )
        assert "entity_type_business_url" not in html_body
        assert "/api/backend/intake-token/qualify/" not in html_body, (
            "No qualify URL must appear in body when template has no tags"
        )

        # Token was still minted (the send proceeded)
        assert _count_tokens_for_lead(lead.id) == 1, (
            "Token must be minted even when body has no merge tags"
        )


# ---------------------------------------------------------------------------
# Test 3: step_key=="5" held for business hours -- no token minted
# ---------------------------------------------------------------------------

class TestE2HeldForBusinessHours:

    def test_no_token_minted_when_held_for_business_hours(self, monkeypatch):
        """
        A step_key=="5" enrollment held for business hours must not mint a token.
        Token minting is gated on the send actually proceeding.
        """
        body_template = '<a href="{{entity_type_individual_url}}">Individual</a>'
        firm = _make_firm(nurture_enabled=True)
        lead = _make_lead(firm.id)

        db = TestingSessionLocal()
        try:
            f = db.query(Firm).filter(Firm.id == firm.id).first()
            f.business_hours_start = 9
            f.business_hours_end = 17
            f.timezone = "UTC"
            db.commit()
        finally:
            db.close()

        seq_id, ver_id, step_id = _make_email_step(firm.id, "5", body_template)

        utc_3am = datetime(2026, 9, 5, 3, 0, 0, tzinfo=timezone.utc)

        class _FixedDatetime:
            @staticmethod
            def now(tz=None):
                return utc_3am

        monkeypatch.setattr("app.services.nurture_execution_service.datetime", _FixedDatetime)

        _make_enrollment(
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
        assert _count_tokens_for_lead(lead.id) == 0, (
            "No token must be minted for a business-hours hold"
        )


# ---------------------------------------------------------------------------
# Test 4: step_key=="5" for toggle-off firm -- excluded before new code runs
# ---------------------------------------------------------------------------

class TestE2ToggleOffFirmExcluded:

    def test_toggle_off_firm_excluded_before_injection(self, monkeypatch):
        """
        A toggle-off firm's step_key=="5" enrollment is excluded at the
        get_due_enrollments query level -- the injection code is never reached.
        """
        firm = _make_firm(nurture_enabled=False)
        lead = _make_lead(firm.id)
        seq_id, ver_id, step_id = _make_email_step(
            firm.id, "5",
            '<a href="{{entity_type_individual_url}}">I</a>'
        )
        _make_enrollment(firm.id, lead.id, seq_id, ver_id, step_id)

        send_calls = []
        monkeypatch.setattr(
            "app.services.nurture_execution_service.EmailService.send_nurture_email",
            lambda **kw: send_calls.append(kw),
        )

        result = run_nurture_tick()

        assert result["checked"] == 0, (
            f"Toggle-off firm enrollment must never be loaded, got checked={result['checked']}"
        )
        assert len(send_calls) == 0
        assert _count_tokens_for_lead(lead.id) == 0, (
            "No token must be minted when firm is toggle-off"
        )


# ---------------------------------------------------------------------------
# Test 5: other step_key -- completely unaffected
# ---------------------------------------------------------------------------

class TestOtherStepKeyUnaffected:

    def test_non_e2_step_does_not_mint_token(self, monkeypatch):
        """
        A due email step with step_key != '5' sends without minting any token.
        Body is sent exactly as rendered (no injection attempted).
        """
        body = "<p>Hello {{unsubscribe_url}} world</p>"
        firm = _make_firm(nurture_enabled=True)
        lead = _make_lead(firm.id)
        seq_id, ver_id, step_id = _make_email_step(firm.id, "3", body)
        _make_enrollment(firm.id, lead.id, seq_id, ver_id, step_id)

        send_calls = []
        monkeypatch.setattr(
            "app.services.nurture_execution_service.EmailService.send_nurture_email",
            lambda **kw: send_calls.append(kw),
        )

        result = run_nurture_tick()

        assert result["sent"] == 1, f"Expected sent=1, got {result}"
        assert len(send_calls) == 1
        html_body = send_calls[0]["html_body"]
        assert "/api/backend/intake-token/qualify/" not in html_body, (
            "Qualify URL must not appear in body for non-step_key-5 email"
        )
        assert _count_tokens_for_lead(lead.id) == 0, (
            "No token must be minted for a non-E2 email step"
        )


# ---------------------------------------------------------------------------
# Test 6: end-to-end -- URL from injected body resolves, entity_type written
# ---------------------------------------------------------------------------

class TestE2EndToEnd:

    def test_injected_url_writes_entity_type_on_lead(self, client, monkeypatch):
        """
        Full loop: tick injects real qualify URL into email body, URL is hit
        against the real /qualify/ endpoint, entity_type is written to Lead,
        and lead.answer_button_clicked fires.
        """
        body_template = (
            '<a href="{{entity_type_individual_url}}">Individual</a>'
            " | "
            '<a href="{{entity_type_business_url}}">Business</a>'
            "{{unsubscribe_url}}"
        )
        firm = _make_firm(nurture_enabled=True)
        lead = _make_lead(firm.id)
        seq_id, ver_id, step_id = _make_email_step(firm.id, "5", body_template)
        _make_enrollment(firm.id, lead.id, seq_id, ver_id, step_id)

        send_calls = []
        monkeypatch.setattr(
            "app.services.nurture_execution_service.EmailService.send_nurture_email",
            lambda **kw: send_calls.append(kw),
        )

        result = run_nurture_tick()
        assert result["sent"] == 1, f"Expected sent=1, got {result}"
        assert len(send_calls) == 1

        html_body = send_calls[0]["html_body"]

        # Extract token from the individual URL
        m = re.search(
            r"/api/backend/intake-token/qualify/([a-f0-9]{64})\?field=entity_type&value=individual",
            html_body,
        )
        assert m is not None, f"Individual URL not found in body: {html_body[:400]}"
        raw_token = m.group(1)

        # Hit the qualify endpoint at the test client path (no /api/backend/ prefix in test)
        r = client.get(
            f"/intake-token/qualify/{raw_token}",
            params={"field": "entity_type", "value": "individual"},
            allow_redirects=False,
        )
        assert r.status_code in (302, 307), (
            f"Qualify endpoint must redirect, got {r.status_code}: {r.text}"
        )

        # entity_type is written to the Lead row
        db = TestingSessionLocal()
        try:
            refreshed = db.query(Lead).filter(Lead.id == lead.id).first()
            assert refreshed.entity_type == "individual", (
                f"entity_type must be 'individual' after qualify click, got {refreshed.entity_type!r}"
            )
        finally:
            db.close()

        # lead.answer_button_clicked event was fired
        from app.models.behavioral_event import BehavioralEvent
        db2 = TestingSessionLocal()
        try:
            event = db2.query(BehavioralEvent).filter(
                BehavioralEvent.event_type == "lead.answer_button_clicked",
                BehavioralEvent.entity_id == lead.id,
            ).first()
            assert event is not None, "lead.answer_button_clicked event must be written"
            assert event.extra_metadata.get("field") == "entity_type"
            assert event.extra_metadata.get("value") == "individual"
        finally:
            db2.close()
