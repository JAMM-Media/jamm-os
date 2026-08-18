# tests/test_intake_endpoint.py

"""
Tests for the public intake form endpoint (POST /intake/{slug}/submit).
Unauthenticated attack surface -- highest priority per Andrew's directive.

Covers:
  - Happy path: Lead creation with crm_lead provenance, UTM capture, behavioral event
  - Tenant isolation: submission to Firm A creates zero data under Firm B
  - Rate limiting: real check_email_rate_limit fires 429 after the 3/15min threshold
  - Input validation: missing required fields, Turnstile failure, verbatim UTM storage

FINDING: UTM values are not validated or sanitized by the intake endpoint.
Garbage or injection-attempt strings are accepted and stored verbatim.
The test_malformed_utm_values_stored_verbatim test asserts this real behavior
rather than a rejection the code does not implement.
"""

import time
import uuid
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.lead import Lead
from app.core.enums import LeadProvenance, SourcePlatform


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm(slug: str, name: str) -> Firm:
    """Create a Firm directly in the test DB. Returns the committed ORM object."""
    db = TestingSessionLocal()
    try:
        firm = Firm(name=name, slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)
        # Cache scalar attributes before session close so they survive detachment.
        _ = firm.id, firm.name, firm.slug
        return firm
    finally:
        db.close()


def _turnstile_mock(success: bool = True):
    """Return a mock for http_requests.post that simulates a Turnstile siteverify response."""
    mock_resp = MagicMock()
    mock_resp.ok = success
    mock_resp.json.return_value = {"success": success}
    return MagicMock(return_value=mock_resp)


def _wait_for_event(firm_id, event_type, timeout: float = 2.0):
    """Poll for a BehavioralEvent row -- the log fires in a background thread."""
    from app.models.behavioral_event import BehavioralEvent
    deadline = time.time() + timeout
    while time.time() < deadline:
        db = TestingSessionLocal()
        try:
            event = (
                db.query(BehavioralEvent)
                .filter(
                    BehavioralEvent.firm_id == firm_id,
                    BehavioralEvent.event_type == event_type,
                )
                .first()
            )
            if event:
                return event
        finally:
            db.close()
        time.sleep(0.05)
    return None


_BASE_PAYLOAD = {
    "name": "Test Prospect",
    "email": "prospect@intake-tests.example.com",
    "turnstile_token": "test-token",
}


@pytest.fixture(autouse=True)
def reset_email_rate_limiter():
    """Clear the in-memory email tracker before and after each test.

    check_email_rate_limit uses module-level state not cleared by clean_db.
    Without this fixture, a 429 test would corrupt the next test's email budget.
    """
    from app.core import rate_limit
    rate_limit._email_tracker.clear()
    yield
    rate_limit._email_tracker.clear()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestIntakeHappyPath:
    def test_creates_lead_with_crm_lead_provenance(self, client):
        firm = _make_firm("hp-firm-1", "Happy Path Firm 1")

        with patch("app.api.intake.http_requests.post", _turnstile_mock()):
            r = client.post(f"/intake/{firm.slug}/submit", json=_BASE_PAYLOAD)

        assert r.status_code == 201

        db = TestingSessionLocal()
        try:
            lead = db.query(Lead).filter(Lead.firm_id == firm.id).first()
            assert lead is not None, "Lead was not created"
            assert lead.name == "Test Prospect"
            assert lead.email == "prospect@intake-tests.example.com"
            assert lead.firm_id == firm.id
            assert lead.provenance == LeadProvenance.crm_lead.value, (
                f"Expected provenance=crm_lead, got {lead.provenance!r}"
            )
        finally:
            db.close()

    def test_captures_utm_parameters_verbatim(self, client):
        firm = _make_firm("hp-firm-2", "Happy Path Firm 2")
        payload = {
            **_BASE_PAYLOAD,
            "email": f"utm-{uuid.uuid4()}@example.com",
            "utm_campaign": "summer-2026",
            "utm_source": "google",
            "utm_medium": "cpc",
            "utm_content": "ad-variant-b",
            "utm_term": "tax+software",
        }

        with patch("app.api.intake.http_requests.post", _turnstile_mock()):
            r = client.post(f"/intake/{firm.slug}/submit", json=payload)

        assert r.status_code == 201

        db = TestingSessionLocal()
        try:
            lead = db.query(Lead).filter(Lead.firm_id == firm.id).first()
            assert lead is not None
            assert lead.utm_campaign == "summer-2026"
            assert lead.utm_source == "google"
            assert lead.utm_medium == "cpc"
            assert lead.utm_content == "ad-variant-b"
            assert lead.utm_term == "tax+software"
        finally:
            db.close()

    def test_fires_lead_created_behavioral_event(self, client):
        firm = _make_firm("hp-firm-3", "Happy Path Firm 3")
        payload = {**_BASE_PAYLOAD, "email": f"event-{uuid.uuid4()}@example.com"}

        with patch("app.api.intake.http_requests.post", _turnstile_mock()):
            r = client.post(f"/intake/{firm.slug}/submit", json=payload)

        assert r.status_code == 201

        event = _wait_for_event(firm.id, "lead.created")
        assert event is not None, "lead.created behavioral event was not fired"


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

class TestIntakeTenantIsolation:
    def test_lead_scoped_to_correct_firm_no_data_under_firm_b(self, client):
        """Submitting to Firm B's slug routes the Lead to Firm B specifically,
        not merely to whichever firm an unfiltered query returns first.

        Both firms exist so insertion order cannot accidentally satisfy the test.
        The assertion requires the SPECIFIC requested firm to receive the data,
        and that the OTHER specific firm received nothing.
        """
        firm_a = _make_firm("isolation-firm-a", "Isolation Firm A")
        firm_b = _make_firm("isolation-firm-b", "Isolation Firm B")

        with patch("app.api.intake.http_requests.post", _turnstile_mock()):
            r = client.post(
                f"/intake/{firm_b.slug}/submit",
                json={**_BASE_PAYLOAD, "email": f"iso-{uuid.uuid4()}@example.com"},
            )

        assert r.status_code == 201

        db = TestingSessionLocal()
        try:
            # Lead must exist under the SPECIFIC firm whose slug was submitted.
            lead_b = db.query(Lead).filter(Lead.firm_id == firm_b.id).first()
            assert lead_b is not None, "Lead not created under Firm B (the requested firm)"
            assert lead_b.firm_id == firm_b.id

            # Explicit assertion: zero rows under Firm A -- the firm that was NOT requested.
            firm_a_count = db.query(Lead).filter(Lead.firm_id == firm_a.id).count()
            assert firm_a_count == 0, (
                f"Tenant isolation breach: {firm_a_count} Lead row(s) found under Firm A"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestIntakeRateLimiting:
    def test_429_after_three_submissions_from_same_email(self, client):
        """Real check_email_rate_limit fires 429 after the 3/15min threshold.

        The IP-based @limiter decorator is disabled in tests (RATE_LIMIT_ENABLED=false).
        check_email_rate_limit uses its own in-memory state and is NOT disabled --
        this test exercises the real function, not a mock.
        """
        firm = _make_firm("ratelimit-firm", "Rate Limit Firm")
        email = f"ratelimit-{uuid.uuid4()}@example.com"

        # First 3 succeed (threshold is max_requests=3)
        for i in range(3):
            with patch("app.api.intake.http_requests.post", _turnstile_mock()):
                r = client.post(
                    f"/intake/{firm.slug}/submit",
                    json={"name": f"Test {i}", "email": email, "turnstile_token": "tok"},
                )
            assert r.status_code == 201, f"Submission {i + 1} unexpectedly failed: {r.json()}"

        # 4th must be rate-limited
        with patch("app.api.intake.http_requests.post", _turnstile_mock()):
            r = client.post(
                f"/intake/{firm.slug}/submit",
                json={"name": "Test 4", "email": email, "turnstile_token": "tok"},
            )

        assert r.status_code == 429, (
            f"Expected 429 on 4th submission, got {r.status_code}: {r.json()}"
        )


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestIntakeInputValidation:
    def test_missing_required_name_rejected_no_lead_created(self, client):
        """Pydantic validation: missing name returns 422, zero Lead rows created."""
        firm = _make_firm("validation-firm-1", "Validation Firm 1")

        with patch("app.api.intake.http_requests.post", _turnstile_mock()):
            r = client.post(
                f"/intake/{firm.slug}/submit",
                json={"email": "noname@example.com", "turnstile_token": "tok"},
            )

        assert r.status_code == 422, f"Expected 422 for missing name, got {r.status_code}"

        db = TestingSessionLocal()
        try:
            count = db.query(Lead).filter(Lead.firm_id == firm.id).count()
            assert count == 0, f"No Lead should exist after validation failure, found {count}"
        finally:
            db.close()

    def test_missing_required_email_rejected_no_lead_created(self, client):
        firm = _make_firm("validation-firm-2", "Validation Firm 2")

        with patch("app.api.intake.http_requests.post", _turnstile_mock()):
            r = client.post(
                f"/intake/{firm.slug}/submit",
                json={"name": "No Email", "turnstile_token": "tok"},
            )

        assert r.status_code == 422

        db = TestingSessionLocal()
        try:
            count = db.query(Lead).filter(Lead.firm_id == firm.id).count()
            assert count == 0
        finally:
            db.close()

    def test_turnstile_failure_rejected_no_lead_created(self, client):
        """A failed Turnstile verification returns 400 and creates no Lead row."""
        firm = _make_firm("validation-firm-3", "Validation Firm 3")

        with patch("app.api.intake.http_requests.post", _turnstile_mock(success=False)):
            r = client.post(f"/intake/{firm.slug}/submit", json=_BASE_PAYLOAD)

        assert r.status_code == 400

        db = TestingSessionLocal()
        try:
            count = db.query(Lead).filter(Lead.firm_id == firm.id).count()
            assert count == 0
        finally:
            db.close()

    def test_unknown_slug_returns_404_no_lead_created(self, client):
        with patch("app.api.intake.http_requests.post", _turnstile_mock()):
            r = client.post("/intake/does-not-exist-at-all/submit", json=_BASE_PAYLOAD)

        assert r.status_code == 404

    def test_malformed_utm_values_stored_verbatim(self, client):
        """FINDING: UTM values are not validated or sanitized.

        Garbage strings (including injection attempts) are accepted and stored
        exactly as submitted. This is the real current behavior. The test asserts
        the real behavior rather than a rejection the code does not implement.
        If UTM validation is added later, this test should be updated or removed.
        """
        firm = _make_firm("validation-firm-4", "Validation Firm 4")
        garbage = "<script>alert('xss')</script>"

        with patch("app.api.intake.http_requests.post", _turnstile_mock()):
            r = client.post(
                f"/intake/{firm.slug}/submit",
                json={
                    "name": "UTM Test",
                    "email": f"garbage-utm-{uuid.uuid4()}@example.com",
                    "turnstile_token": "tok",
                    "utm_campaign": garbage,
                    "utm_source": garbage,
                },
            )

        assert r.status_code == 201, "Garbage UTM values should be accepted verbatim"

        db = TestingSessionLocal()
        try:
            lead = db.query(Lead).filter(Lead.firm_id == firm.id).first()
            assert lead is not None
            assert lead.utm_campaign == garbage, "utm_campaign should be stored verbatim"
            assert lead.utm_source == garbage, "utm_source should be stored verbatim"
        finally:
            db.close()

# ---------------------------------------------------------------------------
# source_platform derivation from utm_source
# ---------------------------------------------------------------------------

class TestSourcePlatformDerivation:
    """Tests for _derive_source_platform and its integration with intake_submit.

    Per Acquisition Tracker section 3.1 Layer 2: source_platform is
    auto-derived from utm_source whenever a lead arrives through a tracked
    link. The derivation is case/whitespace-insensitive and maps common
    variants (fb -> facebook, twitter -> x) to canonical SourcePlatform values.
    """

    def _submit_with_utm_source(self, client, firm, utm_source_value):
        """Helper: submit a lead with the given utm_source, return the created lead."""
        with patch("app.api.intake.http_requests.post", _turnstile_mock()):
            r = client.post(
                f"/intake/{firm.slug}/submit",
                json={
                    "name": "Attribution Test Lead",
                    "email": f"attr-{uuid.uuid4()}@example.com",
                    "turnstile_token": "tok",
                    "utm_source": utm_source_value,
                },
            )
        assert r.status_code == 201, f"Submission failed: {r.text}"
        db = TestingSessionLocal()
        try:
            lead = db.query(Lead).filter(Lead.firm_id == firm.id).order_by(Lead.created_at.desc()).first()
            assert lead is not None
            return lead.source_platform
        finally:
            db.close()

    def test_facebook_utm_source_maps_to_facebook(self, client):
        """utm_source=facebook produces source_platform=facebook."""
        firm = _make_firm(f"plat-fb-{uuid.uuid4().hex[:6]}", "Platform Test FB")
        result = self._submit_with_utm_source(client, firm, "facebook")
        assert result == SourcePlatform.facebook.value, (
            f"Expected facebook, got {result!r}"
        )

    def test_facebook_case_insensitive(self, client):
        """utm_source=' Facebook ' (with spaces and caps) maps to facebook."""
        firm = _make_firm(f"plat-fbc-{uuid.uuid4().hex[:6]}", "Platform Test FB Case")
        result = self._submit_with_utm_source(client, firm, " Facebook ")
        assert result == SourcePlatform.facebook.value, (
            f"Expected facebook from ' Facebook ', got {result!r}"
        )

    def test_fb_alias_maps_to_facebook(self, client):
        """utm_source=FB (alias) maps to facebook."""
        firm = _make_firm(f"plat-fba-{uuid.uuid4().hex[:6]}", "Platform Test FB Alias")
        result = self._submit_with_utm_source(client, firm, "FB")
        assert result == SourcePlatform.facebook.value, (
            f"Expected facebook from 'FB', got {result!r}"
        )

    def test_unrecognized_utm_source_maps_to_other(self, client):
        """An unrecognized utm_source maps to SourcePlatform.other, not null."""
        firm = _make_firm(f"plat-unk-{uuid.uuid4().hex[:6]}", "Platform Test Unknown")
        result = self._submit_with_utm_source(client, firm, "some_random_platform")
        assert result == SourcePlatform.other.value, (
            f"Expected other for unrecognized utm_source, got {result!r}"
        )

    def test_no_utm_source_leaves_source_platform_null(self, client):
        """A submission with no utm_source leaves source_platform as None."""
        firm = _make_firm(f"plat-null-{uuid.uuid4().hex[:6]}", "Platform Test Null")
        with patch("app.api.intake.http_requests.post", _turnstile_mock()):
            r = client.post(
                f"/intake/{firm.slug}/submit",
                json={
                    "name": "No UTM Lead",
                    "email": f"noutm-{uuid.uuid4()}@example.com",
                    "turnstile_token": "tok",
                    # no utm_source field at all
                },
            )
        assert r.status_code == 201
        db = TestingSessionLocal()
        try:
            lead = db.query(Lead).filter(Lead.firm_id == firm.id).first()
            assert lead is not None
            assert lead.source_platform is None, (
                f"Expected source_platform=None when no utm_source, got {lead.source_platform!r}"
            )
        finally:
            db.close()

    def test_cold_outreach_email_value_is_not_producible_from_utm(self, client):
        """GUARD TEST: utm_source='email' must NOT produce SourcePlatform.email.

        SourcePlatform.email (and phone, dm, direct_mail) are reserved for the
        cold_outreach mechanism per the enum's own docstring -- they describe how
        a cold_outreach lead was contacted, not a web platform a UTM tag identifies.
        A lead arriving through a web form with utm_source='email' gets
        SourcePlatform.other, never SourcePlatform.email. This test exists to
        prevent accidental future regressions that would expose the reserved values
        via the UTM derivation path.
        """
        firm = _make_firm(f"plat-guard-{uuid.uuid4().hex[:6]}", "Platform Guard Test")
        result = self._submit_with_utm_source(client, firm, "email")
        # Must not be SourcePlatform.email -- that value is reserved for cold_outreach.
        assert result != SourcePlatform.email.value, (
            "utm_source='email' must never produce SourcePlatform.email -- "
            "that value is reserved for the cold_outreach mechanism."
        )
        # Should fall through to SourcePlatform.other since 'email' is not in the mapping.
        assert result == SourcePlatform.other.value, (
            f"utm_source='email' should map to SourcePlatform.other, got {result!r}"
        )

    def test_phone_dm_direct_mail_also_map_to_other_not_reserved(self, client):
        """The other three reserved cold_outreach values are also not producible from UTM."""
        firm = _make_firm(f"plat-rsv-{uuid.uuid4().hex[:6]}", "Platform Reserved Test")
        reserved = ("phone", "dm", "direct_mail")
        for val in reserved:
            result = self._submit_with_utm_source(client, firm, val)
            assert result == SourcePlatform.other.value, (
                f"utm_source={val!r} must not produce SourcePlatform.{val} -- "
                f"that value is reserved for cold_outreach. Got {result!r}"
            )
