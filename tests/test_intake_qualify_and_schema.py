# tests/test_intake_qualify_and_schema.py

"""
Tests for the E2 qualify endpoint, service_interest schema validation,
and E2 button URL injection in nurture_execution_service.py.

Covers:
  1. field=entity_type&value=individual writes entity_type="individual" onto Lead.
  2. field=entity_type&value=business writes entity_type="business".
  3. Invalid value (not one of the five real values) returns 422, writes nothing.
  4. Non-whitelisted field (e.g. field=service_interest) returns 422, writes nothing.
  5. Invalid/expired token redirects to intake-resume page (not 401 or 404).
  6. Token remains valid after a qualify click (NOT single-use).
  7. lead.answer_button_clicked fires with correct metadata on success; does not
     fire on a rejected request.
  8. Tenant isolation: Firm A token cannot write entity_type on Firm B's lead.
  9. service_interest schema validation: valid EngagementType accepted; arbitrary
     string rejected with 422 on both LeadCreate and LeadUpdate paths.
  10. E2 email body with merge tags gets correctly-formed qualify URLs injected;
      body without tags sends unchanged.
  11. Regression: existing intake_token, intake_endpoint, nurture suites pass.
"""

import hashlib
import re
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from tests.conftest import TestingSessionLocal
from app.core.enums import LeadProvenance, EngagementType
from app.models.firm import Firm
from app.models.lead import Lead
from app.models.lead_intake_token import LeadIntakeToken
from app.services.intake_token_service import mint_intake_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm(slug: str) -> Firm:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Qualify Firm {slug}", slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)
        return firm
    finally:
        db.close()


def _make_lead(firm_id: uuid.UUID) -> Lead:
    db = TestingSessionLocal()
    try:
        lead = Lead(
            firm_id=firm_id,
            name="Qualify Test Lead",
            email=f"lead-{uuid.uuid4().hex[:8]}@example.com",
            stage="identified",
            provenance=LeadProvenance.crm_lead,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        return lead
    finally:
        db.close()


def _make_firm_and_owner(slug: str):
    from app.core.security import get_password_hash
    from app.core.enums import UserRole
    from app.models.user import User

    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Owner Firm {slug}", slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)

        from app.services.tax_organizer_service import seed_firm_organizer_templates
        seed_firm_organizer_templates(firm_id=firm.id, db=db)

        email = f"owner-{slug}@example.com"
        user = User(
            firm_id=firm.id,
            email=email,
            hashed_password=get_password_hash("pass1234"),
            full_name="Test Owner",
            role=UserRole.firm_owner,
        )
        db.add(user)
        db.commit()
        return firm, user, email
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1 & 2. Valid qualify clicks write entity_type onto the Lead row
# ---------------------------------------------------------------------------

class TestQualifyWritesEntityType:

    def test_individual_value_writes_to_lead(self, client):
        """GET /qualify/{token}?field=entity_type&value=individual writes entity_type='individual'."""
        firm = _make_firm(f"qual-ind-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        db = TestingSessionLocal()
        try:
            raw_token = mint_intake_token(db=db, firm_id=firm.id, lead_id=lead.id)
        finally:
            db.close()

        r = client.get(
            f"/intake-token/qualify/{raw_token}",
            params={"field": "entity_type", "value": "individual"},
            allow_redirects=False,
        )
        assert r.status_code in (302, 307), f"Expected redirect, got {r.status_code}: {r.text}"

        db2 = TestingSessionLocal()
        try:
            refreshed = db2.query(Lead).filter(Lead.id == lead.id).first()
            assert refreshed.entity_type == "individual", (
                f"entity_type must be 'individual' after qualify click, got {refreshed.entity_type!r}"
            )
        finally:
            db2.close()

    def test_business_value_writes_to_lead(self, client):
        """GET /qualify/{token}?field=entity_type&value=business writes entity_type='business'."""
        firm = _make_firm(f"qual-biz-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        db = TestingSessionLocal()
        try:
            raw_token = mint_intake_token(db=db, firm_id=firm.id, lead_id=lead.id)
        finally:
            db.close()

        r = client.get(
            f"/intake-token/qualify/{raw_token}",
            params={"field": "entity_type", "value": "business"},
            allow_redirects=False,
        )
        assert r.status_code in (302, 307)

        db2 = TestingSessionLocal()
        try:
            refreshed = db2.query(Lead).filter(Lead.id == lead.id).first()
            assert refreshed.entity_type == "business"
        finally:
            db2.close()

    def test_all_five_entity_type_values_are_accepted(self, client):
        """All five real entity_type values are accepted by the qualify endpoint."""
        for et_value in ("individual", "business", "trust", "estate", "non_profit"):
            firm = _make_firm(f"qual-all-{et_value}-{uuid.uuid4().hex[:4]}")
            lead = _make_lead(firm.id)

            db = TestingSessionLocal()
            try:
                raw_token = mint_intake_token(db=db, firm_id=firm.id, lead_id=lead.id)
            finally:
                db.close()

            r = client.get(
                f"/intake-token/qualify/{raw_token}",
                params={"field": "entity_type", "value": et_value},
                allow_redirects=False,
            )
            assert r.status_code in (302, 307), (
                f"Value {et_value!r} must be accepted, got {r.status_code}"
            )


# ---------------------------------------------------------------------------
# 3. Invalid value returns 422, writes nothing
# ---------------------------------------------------------------------------

class TestInvalidValueReturns422:

    def test_invalid_entity_type_value_returns_422(self, client):
        """A value not in the five real entity_type values returns 422."""
        firm = _make_firm(f"qual-inv-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        db = TestingSessionLocal()
        try:
            raw_token = mint_intake_token(db=db, firm_id=firm.id, lead_id=lead.id)
        finally:
            db.close()

        r = client.get(
            f"/intake-token/qualify/{raw_token}",
            params={"field": "entity_type", "value": "corporation"},  # not a real value
            allow_redirects=False,
        )
        assert r.status_code == 422, (
            f"Invalid value must return 422, got {r.status_code}: {r.text}"
        )

        # Nothing was written
        db2 = TestingSessionLocal()
        try:
            refreshed = db2.query(Lead).filter(Lead.id == lead.id).first()
            assert refreshed.entity_type is None, (
                f"entity_type must be null after rejected request, got {refreshed.entity_type!r}"
            )
        finally:
            db2.close()


# ---------------------------------------------------------------------------
# 4. Non-whitelisted field returns 422, writes nothing
# ---------------------------------------------------------------------------

class TestNonWhitelistedFieldReturns422:

    def test_service_interest_field_rejected(self, client):
        """field=service_interest is not in the whitelist and returns 422."""
        firm = _make_firm(f"qual-wl-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        db = TestingSessionLocal()
        try:
            raw_token = mint_intake_token(db=db, firm_id=firm.id, lead_id=lead.id)
        finally:
            db.close()

        r = client.get(
            f"/intake-token/qualify/{raw_token}",
            params={"field": "service_interest", "value": "tax_return_1040"},
            allow_redirects=False,
        )
        assert r.status_code == 422, (
            f"Non-whitelisted field must return 422, got {r.status_code}: {r.text}"
        )

    def test_arbitrary_field_rejected(self, client):
        """field=stage is not in the whitelist and returns 422."""
        firm = _make_firm(f"qual-arb-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        db = TestingSessionLocal()
        try:
            raw_token = mint_intake_token(db=db, firm_id=firm.id, lead_id=lead.id)
        finally:
            db.close()

        r = client.get(
            f"/intake-token/qualify/{raw_token}",
            params={"field": "stage", "value": "won"},
            allow_redirects=False,
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# 5. Invalid/expired token redirects to intake-resume (not 401/404)
# ---------------------------------------------------------------------------

class TestExpiredTokenRedirects:

    def test_expired_token_redirects_to_intake_resume(self, client):
        """An expired token redirects to the intake-resume page, not a 401 or 404."""
        import secrets
        raw_token = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        firm = _make_firm(f"qual-exp-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        db = TestingSessionLocal()
        try:
            expired_row = LeadIntakeToken(
                firm_id=firm.id,
                lead_id=lead.id,
                token_hash=token_hash,
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
            db.add(expired_row)
            db.commit()
        finally:
            db.close()

        r = client.get(
            f"/intake-token/qualify/{raw_token}",
            params={"field": "entity_type", "value": "individual"},
            allow_redirects=False,
        )
        assert r.status_code in (302, 307), (
            f"Expired token must redirect (302/307), got {r.status_code}: {r.text}"
        )
        location = r.headers.get("location", "")
        assert "/intake-resume/" in location, (
            f"Redirect must target /intake-resume/..., got: {location!r}"
        )
        assert raw_token in location, "Token must be in the redirect URL"

    def test_unknown_token_redirects_not_404(self, client):
        """A completely unknown token redirects (not 404)."""
        r = client.get(
            "/intake-token/qualify/totallybogustoken",
            params={"field": "entity_type", "value": "individual"},
            allow_redirects=False,
        )
        assert r.status_code in (302, 307), (
            f"Unknown token must redirect, not {r.status_code}"
        )


# ---------------------------------------------------------------------------
# 6. Token is NOT invalidated after a qualify click
# ---------------------------------------------------------------------------

class TestTokenNotInvalidatedByQualify:

    def test_token_valid_after_qualify_click(self, client):
        """The token survives a qualify click and can be used again (NOT single-use)."""
        firm = _make_firm(f"qual-nosingle-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        db = TestingSessionLocal()
        try:
            raw_token = mint_intake_token(db=db, firm_id=firm.id, lead_id=lead.id)
        finally:
            db.close()

        # First qualify click
        client.get(
            f"/intake-token/qualify/{raw_token}",
            params={"field": "entity_type", "value": "individual"},
            allow_redirects=False,
        )

        # Token must still validate
        r2 = client.get(f"/intake-token/validate/{raw_token}")
        assert r2.json()["status"] == "valid", (
            "Token must remain valid after a qualify click -- "
            f"got status={r2.json()['status']!r}"
        )


# ---------------------------------------------------------------------------
# 7. lead.answer_button_clicked fires on success, not on rejection
# ---------------------------------------------------------------------------

class TestAnswerButtonClickedEvent:

    def test_event_fires_with_correct_metadata_on_success(self, client):
        """lead.answer_button_clicked fires with correct firm_id, entity_id, metadata."""
        firm = _make_firm(f"qual-event-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        db = TestingSessionLocal()
        try:
            raw_token = mint_intake_token(db=db, firm_id=firm.id, lead_id=lead.id)
        finally:
            db.close()

        fired_calls = []

        def capture_log_event(**kwargs):
            fired_calls.append(kwargs)

        with patch("app.api.intake_token.log_event", side_effect=capture_log_event):
            r = client.get(
                f"/intake-token/qualify/{raw_token}",
                params={"field": "entity_type", "value": "trust"},
                allow_redirects=False,
            )

        assert r.status_code in (302, 307)
        assert len(fired_calls) == 1, f"Expected 1 log_event call, got {len(fired_calls)}"
        call = fired_calls[0]
        assert call["event_type"] == "lead.answer_button_clicked"
        assert call["firm_id"] == firm.id
        assert call["entity_id"] == lead.id
        assert call["actor_type"] == "lead"
        assert call["metadata"]["field"] == "entity_type"
        assert call["metadata"]["value"] == "trust"

    def test_event_does_not_fire_on_invalid_value(self, client):
        """log_event must NOT fire when the value is rejected with 422."""
        firm = _make_firm(f"qual-noevent-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        db = TestingSessionLocal()
        try:
            raw_token = mint_intake_token(db=db, firm_id=firm.id, lead_id=lead.id)
        finally:
            db.close()

        fired_calls = []

        def capture_log_event(**kwargs):
            fired_calls.append(kwargs)

        with patch("app.api.intake_token.log_event", side_effect=capture_log_event):
            r = client.get(
                f"/intake-token/qualify/{raw_token}",
                params={"field": "entity_type", "value": "not_a_real_value"},
                allow_redirects=False,
            )

        assert r.status_code == 422
        assert len(fired_calls) == 0, "log_event must not fire on a rejected request"

    def test_event_does_not_fire_on_non_whitelisted_field(self, client):
        """log_event must NOT fire when the field is rejected with 422."""
        firm = _make_firm(f"qual-noevent2-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        db = TestingSessionLocal()
        try:
            raw_token = mint_intake_token(db=db, firm_id=firm.id, lead_id=lead.id)
        finally:
            db.close()

        fired_calls = []

        def capture_log_event(**kwargs):
            fired_calls.append(kwargs)

        with patch("app.api.intake_token.log_event", side_effect=capture_log_event):
            r = client.get(
                f"/intake-token/qualify/{raw_token}",
                params={"field": "revenue_band", "value": "100k-500k"},
                allow_redirects=False,
            )

        assert r.status_code == 422
        assert len(fired_calls) == 0


# ---------------------------------------------------------------------------
# 8. Tenant isolation
# ---------------------------------------------------------------------------

class TestTenantIsolation:

    def test_firm_a_token_cannot_write_firm_b_lead(self, client):
        """A token minted for Firm A cannot write entity_type on Firm B's lead."""
        firm_a = _make_firm(f"qual-iso-a-{uuid.uuid4().hex[:6]}")
        firm_b = _make_firm(f"qual-iso-b-{uuid.uuid4().hex[:6]}")
        lead_a = _make_lead(firm_a.id)
        lead_b = _make_lead(firm_b.id)

        db = TestingSessionLocal()
        try:
            raw_token_a = mint_intake_token(db=db, firm_id=firm_a.id, lead_id=lead_a.id)
        finally:
            db.close()

        # Use Firm A's token -- it will resolve to Firm A's lead and write there
        r = client.get(
            f"/intake-token/qualify/{raw_token_a}",
            params={"field": "entity_type", "value": "business"},
            allow_redirects=False,
        )
        assert r.status_code in (302, 307)

        # Firm B's lead is untouched
        db2 = TestingSessionLocal()
        try:
            b = db2.query(Lead).filter(Lead.id == lead_b.id).first()
            assert b.entity_type is None, "Firm B's lead must not be modified"
            a = db2.query(Lead).filter(Lead.id == lead_a.id).first()
            assert a.entity_type == "business", "Firm A's lead must be written"
        finally:
            db2.close()


# ---------------------------------------------------------------------------
# 9. service_interest schema validation
# ---------------------------------------------------------------------------

class TestServiceInterestValidation:

    def test_valid_engagement_type_accepted_on_create(self, client, firm_a_owner):
        """A valid EngagementType value is accepted on LeadCreate."""
        from app.schemas.lead import LeadCreate
        from app.core.enums import LeadProvenance

        payload = LeadCreate(
            name="Schema Test Lead",
            email="schema@test.com",
            service_interest="tax_return_1040",
            provenance=LeadProvenance.firm_entered,
        )
        assert payload.service_interest == "tax_return_1040"

    def test_invalid_service_interest_rejected_on_create(self, client, firm_a_owner):
        """An arbitrary string for service_interest is rejected with ValueError."""
        from app.schemas.lead import LeadCreate
        from app.core.enums import LeadProvenance
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            LeadCreate(
                name="Schema Test Lead",
                email="schema@test.com",
                service_interest="make_me_rich",
                provenance=LeadProvenance.firm_entered,
            )
        assert "service_interest" in str(exc_info.value).lower() or "EngagementType" in str(exc_info.value)

    def test_invalid_service_interest_rejected_on_update_via_api(self, client, firm_a_owner):
        """PATCH /api/v1/leads/{id} returns 422 for an invalid service_interest value."""
        firm_id = uuid.UUID(firm_a_owner["firm_id"])
        lead = _make_lead(firm_id)

        r = client.patch(
            f"/api/v1/leads/{lead.id}",
            json={"service_interest": "make_me_rich"},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422, (
            f"Invalid service_interest must return 422 via API, got {r.status_code}: {r.text}"
        )

    def test_valid_service_interest_accepted_on_update_via_api(self, client, firm_a_owner):
        """PATCH /api/v1/leads/{id} accepts a valid EngagementType value."""
        firm_id = uuid.UUID(firm_a_owner["firm_id"])
        lead = _make_lead(firm_id)

        r = client.patch(
            f"/api/v1/leads/{lead.id}",
            json={"service_interest": "bookkeeping_monthly"},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 200, f"Valid service_interest must be accepted, got {r.status_code}: {r.text}"

    def test_none_service_interest_accepted(self):
        """None (absent field) is always accepted on both create and update."""
        from app.schemas.lead import LeadCreate, LeadUpdate
        from app.core.enums import LeadProvenance

        create = LeadCreate(name="Test", provenance=LeadProvenance.firm_entered, service_interest=None)
        assert create.service_interest is None

        update = LeadUpdate(service_interest=None)
        assert update.service_interest is None

    def test_all_engagement_type_members_accepted(self):
        """Every single EngagementType member is accepted by the validator."""
        from app.schemas.lead import LeadCreate
        from app.core.enums import LeadProvenance

        for et in EngagementType:
            payload = LeadCreate(
                name="Test",
                provenance=LeadProvenance.firm_entered,
                service_interest=et.value,
            )
            assert payload.service_interest == et.value, (
                f"EngagementType member {et.value!r} was rejected by the validator"
            )


# ---------------------------------------------------------------------------
# 10. E2 email body injection in nurture_execution_service
# ---------------------------------------------------------------------------

class TestE2ButtonInjection:

    def _make_e2_sequence(self, firm_id):
        """Create a minimal sequence with a step_key='5' email step."""
        from app.core.enums import StepType
        from app.models.sequence import Sequence, SequenceVersion, Step, StepEdge

        db = TestingSessionLocal()
        try:
            now = datetime.now(timezone.utc)
            seq = Sequence(
                firm_id=firm_id, name="E2 Test Seq", is_active=True,
                created_at=now, updated_at=now,
            )
            db.add(seq)
            db.flush()
            ver = SequenceVersion(
                sequence_id=seq.id, version_number=1,
                preset_lineage_key="e2_test", created_at=now,
            )
            db.add(ver)
            db.flush()
            email_step = Step(
                sequence_version_id=ver.id,
                step_key="5",
                step_type=StepType.email,
                channel="email",
                config={
                    "subject": "Quick question",
                    "body": (
                        "Are you an individual or a business? "
                        '<a href="{{entity_type_individual_url}}">I am an individual</a> '
                        '<a href="{{entity_type_business_url}}">I am a business</a> '
                        '{{unsubscribe_url}}'
                    ),
                },
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
            return seq.id, ver.id, email_step.id
        finally:
            db.close()

    def _make_enrollment(self, firm_id, lead_id, seq_id, ver_id, step_id):
        from app.models.enrollment import Enrollment
        from app.core.enums import EnrollmentStatus

        db = TestingSessionLocal()
        try:
            now = datetime.now(timezone.utc)
            e = Enrollment(
                firm_id=firm_id,
                lead_id=lead_id,
                sequence_id=seq_id,
                sequence_version_id=ver_id,
                current_step_id=step_id,
                next_action_time=now - timedelta(seconds=1),
                status=EnrollmentStatus.active,
                enrolled_at=now,
                loop_counts={},
            )
            db.add(e)
            db.commit()
            db.refresh(e)
            return e
        finally:
            db.close()

    def test_e2_body_with_tags_gets_inject_urls(self, monkeypatch):
        """E2 step body with {{entity_type_individual_url}} and {{entity_type_business_url}}
        gets two real, correctly-formed qualify URLs injected."""
        captured_bodies = []

        def capture_send(**kw):
            captured_bodies.append(kw.get("html_body", ""))

        monkeypatch.setattr(
            "app.services.nurture_execution_service.EmailService.send_nurture_email",
            capture_send,
        )

        from app.services.nurture_execution_service import run_nurture_tick
        from app.models.lead import Lead

        db = TestingSessionLocal()
        try:
            firm = Firm(name="E2 Inject Firm", slug=f"e2-inject-{uuid.uuid4().hex[:6]}")
            db.add(firm)
            db.flush()
            firm.business_hours_start = 0
            firm.business_hours_end = 24
            firm.timezone = "UTC"
            lead = Lead(
                firm_id=firm.id,
                name="E2 Test Lead",
                email=f"e2-{uuid.uuid4().hex[:8]}@example.com",
                stage="identified",
                provenance=LeadProvenance.crm_lead,
            )
            db.add(lead)
            db.commit()
            firm_id = firm.id
            lead_id = lead.id
        finally:
            db.close()

        seq_id, ver_id, step_id = self._make_e2_sequence(firm_id)
        self._make_enrollment(firm_id, lead_id, seq_id, ver_id, step_id)

        run_nurture_tick()

        assert len(captured_bodies) == 1, f"Expected 1 email sent, got {len(captured_bodies)}"
        body = captured_bodies[0]

        # Both tags must be replaced by real qualify URLs
        assert "{{entity_type_individual_url}}" not in body, "individual tag must be replaced"
        assert "{{entity_type_business_url}}" not in body, "business tag must be replaced"

        # URLs must match the expected pattern
        individual_matches = re.findall(
            r'https?://[^"<\s]+/intake-token/qualify/([a-f0-9]{64})\?field=entity_type&value=individual',
            body,
        )
        business_matches = re.findall(
            r'https?://[^"<\s]+/intake-token/qualify/([a-f0-9]{64})\?field=entity_type&value=business',
            body,
        )
        assert len(individual_matches) == 1, f"Expected 1 individual URL, body={body[:300]!r}"
        assert len(business_matches) == 1, f"Expected 1 business URL, body={body[:300]!r}"

        # Both URLs must use the SAME token (one mint per E2 send)
        assert individual_matches[0] == business_matches[0], (
            "individual and business URLs must use the same token"
        )

        # The injected token must be a real, valid LeadIntakeToken in the DB
        injected_token = individual_matches[0]
        token_hash = hashlib.sha256(injected_token.encode()).hexdigest()
        db3 = TestingSessionLocal()
        try:
            row = db3.query(LeadIntakeToken).filter(
                LeadIntakeToken.token_hash == token_hash
            ).first()
            assert row is not None, "Injected token must exist as a LeadIntakeToken row"
            assert row.firm_id == firm_id
            assert row.lead_id == lead_id
        finally:
            db3.close()

    def test_e2_body_without_tags_sends_unchanged(self, monkeypatch):
        """E2 step body without the merge tags sends without forced button append."""
        captured_bodies = []

        def capture_send(**kw):
            captured_bodies.append(kw.get("html_body", ""))

        monkeypatch.setattr(
            "app.services.nurture_execution_service.EmailService.send_nurture_email",
            capture_send,
        )

        from app.services.nurture_execution_service import run_nurture_tick
        from app.core.enums import StepType
        from app.models.sequence import Sequence, SequenceVersion, Step, StepEdge
        from app.models.enrollment import Enrollment
        from app.core.enums import EnrollmentStatus

        db = TestingSessionLocal()
        try:
            firm = Firm(name="E2 No-tag Firm", slug=f"e2-notag-{uuid.uuid4().hex[:6]}")
            db.add(firm)
            db.flush()
            firm.business_hours_start = 0
            firm.business_hours_end = 24
            firm.timezone = "UTC"
            lead = Lead(
                firm_id=firm.id,
                name="No-tag Lead",
                email=f"notag-{uuid.uuid4().hex[:8]}@example.com",
                stage="identified",
                provenance=LeadProvenance.crm_lead,
            )
            db.add(lead)
            db.flush()
            now = datetime.now(timezone.utc)
            seq = Sequence(
                firm_id=firm.id, name="No-tag Seq", is_active=True,
                created_at=now, updated_at=now,
            )
            db.add(seq)
            db.flush()
            ver = SequenceVersion(
                sequence_id=seq.id, version_number=1,
                preset_lineage_key="notag_test", created_at=now,
            )
            db.add(ver)
            db.flush()
            # step_key="5" but body has NO merge tags
            original_body = "Hello, what brings you here? {{unsubscribe_url}}"
            email_step = Step(
                sequence_version_id=ver.id,
                step_key="5",
                step_type=StepType.email,
                channel="email",
                config={"subject": "E2", "body": original_body},
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
            edge = StepEdge(from_step_id=email_step.id, to_step_id=done_step.id, created_at=now)
            db.add(edge)
            seq.current_version_id = ver.id
            e = Enrollment(
                firm_id=firm.id,
                lead_id=lead.id,
                sequence_id=seq.id,
                sequence_version_id=ver.id,
                current_step_id=email_step.id,
                next_action_time=now - timedelta(seconds=1),
                status=EnrollmentStatus.active,
                enrolled_at=now,
                loop_counts={},
            )
            db.add(e)
            db.commit()
        finally:
            db.close()

        run_nurture_tick()

        assert len(captured_bodies) == 1
        body = captured_bodies[0]
        # The body must not contain qualify URLs (no tags, no forced append)
        assert "intake-token/qualify" not in body, (
            "qualify URL must NOT be appended when body has no merge tags"
        )
