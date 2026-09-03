# tests/test_intake_token.py

"""
Tests for the intake answer table and lead intake token system.

Covers:
  1. Each of the four IntakeAnswer kinds writes correctly with the right fields
     populated and the right fields null.
  2. dimension_categorical rows require both dimension_key and value_option_id.
  3. Token minting stores only the SHA-256 hash, never the raw token.
  4. Token validation resolves lead_id and firm_id from the token row only.
  5. An expired token returns the neutral-200 invalid shape, not 401/404.
  6. A used-but-not-expired token remains valid for a second request (NOT single-use).
  7. Rate limiting: @limiter is disabled in tests (RATE_LIMIT_ENABLED=false);
     endpoints respond correctly without triggering 429.
  8. Tenant isolation: a token minted for Firm A cannot be used for Firm B.
  9. Regression: full existing intake, nurture_execution, and unsubscribe suites.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import TestingSessionLocal
from app.core.enums import LeadProvenance
from app.models.firm import Firm
from app.models.intake_answer import IntakeAnswer
from app.models.lead import Lead
from app.models.lead_intake_token import LeadIntakeToken
from app.services.intake_token_service import (
    mint_intake_token,
    validate_intake_token,
)


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
        return firm
    finally:
        db.close()


def _make_lead(firm_id: uuid.UUID) -> Lead:
    db = TestingSessionLocal()
    try:
        lead = Lead(
            firm_id=firm_id,
            name="Token Test Lead",
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


def _staff_login(http_client, email: str, password: str = "pass1234") -> dict:
    r = http_client.post("/auth/token", json={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_firm_and_owner(slug: str) -> tuple:
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
        db.refresh(user)
        return firm, user, email
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1. IntakeAnswer kinds write correctly
# ---------------------------------------------------------------------------

class TestIntakeAnswerKinds:

    def test_flag_kind_writes_correctly(self):
        """flag: dimension_key null, all value_* null."""
        firm = _make_firm(f"ia-flag-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        db = TestingSessionLocal()
        try:
            row = IntakeAnswer(
                firm_id=firm.id,
                lead_id=lead.id,
                kind="flag",
                dimension_key=None,
                value_option_id=None,
                value_numeric=None,
                value_boolean=None,
                value_text=None,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            assert row.kind == "flag"
            assert row.dimension_key is None
            assert row.value_option_id is None
            assert row.value_numeric is None
            assert row.value_boolean is None
            assert row.value_text is None
        finally:
            db.close()

    def test_dimension_numeric_writes_correctly(self):
        """dimension_numeric: dimension_key and value_numeric set; others null."""
        firm = _make_firm(f"ia-num-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        db = TestingSessionLocal()
        try:
            row = IntakeAnswer(
                firm_id=firm.id,
                lead_id=lead.id,
                kind="dimension_numeric",
                dimension_key="annual_revenue",
                value_numeric=500000.00,
                value_option_id=None,
                value_boolean=None,
                value_text=None,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            assert row.kind == "dimension_numeric"
            assert row.dimension_key == "annual_revenue"
            assert float(row.value_numeric) == pytest.approx(500000.00)
            assert row.value_option_id is None
            assert row.value_boolean is None
            assert row.value_text is None
        finally:
            db.close()

    def test_dimension_categorical_writes_correctly(self):
        """dimension_categorical: dimension_key and value_option_id both set."""
        firm = _make_firm(f"ia-cat-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        option_id = uuid.uuid4()

        db = TestingSessionLocal()
        try:
            row = IntakeAnswer(
                firm_id=firm.id,
                lead_id=lead.id,
                kind="dimension_categorical",
                dimension_key="entity_type",
                value_option_id=option_id,
                value_numeric=None,
                value_boolean=None,
                value_text=None,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            assert row.kind == "dimension_categorical"
            assert row.dimension_key == "entity_type"
            assert row.value_option_id == option_id
            assert row.value_numeric is None
            assert row.value_boolean is None
            assert row.value_text is None
        finally:
            db.close()

    def test_dimension_categorical_with_other_text(self):
        """dimension_categorical Other option: value_text populated alongside option_id."""
        firm = _make_firm(f"ia-catext-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        option_id = uuid.uuid4()

        db = TestingSessionLocal()
        try:
            row = IntakeAnswer(
                firm_id=firm.id,
                lead_id=lead.id,
                kind="dimension_categorical",
                dimension_key="service_interest",
                value_option_id=option_id,
                value_text="International tax planning",
                value_numeric=None,
                value_boolean=None,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            assert row.kind == "dimension_categorical"
            assert row.value_text == "International tax planning"
            assert row.value_option_id == option_id
        finally:
            db.close()

    def test_dimension_boolean_writes_correctly(self):
        """dimension_boolean: dimension_key and value_boolean set; others null."""
        firm = _make_firm(f"ia-bool-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        db = TestingSessionLocal()
        try:
            row = IntakeAnswer(
                firm_id=firm.id,
                lead_id=lead.id,
                kind="dimension_boolean",
                dimension_key="has_inventory",
                value_boolean=True,
                value_option_id=None,
                value_numeric=None,
                value_text=None,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            assert row.kind == "dimension_boolean"
            assert row.dimension_key == "has_inventory"
            assert row.value_boolean is True
            assert row.value_option_id is None
            assert row.value_numeric is None
            assert row.value_text is None
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 2. Categorical rows require both dimension_key and value_option_id
# ---------------------------------------------------------------------------

class TestCategoricalConsistency:

    def test_categorical_without_value_option_id_is_rejected_at_api(self, client, firm_a_owner):
        """POST /intake-token/answers/{token} rejects dimension_categorical missing value_option_id."""
        firm_id = uuid.UUID(firm_a_owner["firm_id"])
        lead = _make_lead(firm_id)

        db = TestingSessionLocal()
        try:
            raw_token = mint_intake_token(db=db, firm_id=firm_id, lead_id=lead.id)
        finally:
            db.close()

        r = client.post(
            f"/intake-token/answers/{raw_token}",
            json={
                "answers": [
                    {
                        "kind": "dimension_categorical",
                        "dimension_key": "entity_type",
                        "value_option_id": None,
                    }
                ]
            },
        )
        assert r.status_code == 422, r.text

    def test_categorical_without_dimension_key_is_rejected_at_api(self, client, firm_a_owner):
        """POST /intake-token/answers/{token} rejects dimension_categorical missing dimension_key."""
        firm_id = uuid.UUID(firm_a_owner["firm_id"])
        lead = _make_lead(firm_id)

        db = TestingSessionLocal()
        try:
            raw_token = mint_intake_token(db=db, firm_id=firm_id, lead_id=lead.id)
        finally:
            db.close()

        r = client.post(
            f"/intake-token/answers/{raw_token}",
            json={
                "answers": [
                    {
                        "kind": "dimension_categorical",
                        "dimension_key": None,
                        "value_option_id": str(uuid.uuid4()),
                    }
                ]
            },
        )
        assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# 3. Token minting stores only the SHA-256 hash
# ---------------------------------------------------------------------------

class TestTokenMintingHashOnly:

    def test_mint_stores_hash_not_raw_token(self):
        """mint_intake_token returns the raw token but only stores the SHA-256 hash."""
        firm = _make_firm(f"tok-hash-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        db = TestingSessionLocal()
        try:
            raw_token = mint_intake_token(db=db, firm_id=firm.id, lead_id=lead.id)
            expected_hash = hashlib.sha256(raw_token.encode()).hexdigest()

            row = db.query(LeadIntakeToken).filter(
                LeadIntakeToken.lead_id == lead.id,
                LeadIntakeToken.firm_id == firm.id,
            ).first()

            assert row is not None, "LeadIntakeToken row not created"
            assert row.token_hash == expected_hash, (
                "Stored hash does not match SHA-256 of returned raw token"
            )
            assert row.token_hash != raw_token, (
                "Raw token must never be stored -- only the hash"
            )
            assert len(row.token_hash) == 64, "SHA-256 hex digest must be 64 chars"
        finally:
            db.close()

    def test_mint_sets_correct_expiry(self):
        """Minted token expires approximately INTAKE_TOKEN_EXPIRE_DAYS from now."""
        from app.core.config import get_settings
        settings = get_settings()

        firm = _make_firm(f"tok-exp-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        db = TestingSessionLocal()
        try:
            mint_intake_token(db=db, firm_id=firm.id, lead_id=lead.id)
            row = db.query(LeadIntakeToken).filter(
                LeadIntakeToken.lead_id == lead.id
            ).first()
            days_remaining = (row.expires_at - datetime.now(timezone.utc)).days
            expected = settings.INTAKE_TOKEN_EXPIRE_DAYS
            assert expected - 1 <= days_remaining <= expected, (
                f"Expected ~{expected} days, got {days_remaining}"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 4. Token validation resolves lead_id and firm_id from the token row only
# ---------------------------------------------------------------------------

class TestTokenValidation:

    def test_validate_resolves_lead_and_firm_from_token_row(self):
        """validate_intake_token returns lead_id and firm_id matching the DB row."""
        firm = _make_firm(f"tok-val-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        db = TestingSessionLocal()
        try:
            raw_token = mint_intake_token(db=db, firm_id=firm.id, lead_id=lead.id)
            result = validate_intake_token(db=db, raw_token=raw_token)
        finally:
            db.close()

        assert result["status"] == "valid"
        assert result["lead_id"] == str(lead.id)
        assert result["firm_id"] == str(firm.id)

    def test_validate_unknown_token_returns_invalid(self):
        """A completely made-up token returns status='invalid'."""
        db = TestingSessionLocal()
        try:
            result = validate_intake_token(db=db, raw_token="notarealtokenabc123" * 4)
        finally:
            db.close()

        assert result["status"] == "invalid"
        assert result["lead_id"] is None
        assert result["firm_id"] is None


# ---------------------------------------------------------------------------
# 5. Expired token returns neutral-200 invalid shape
# ---------------------------------------------------------------------------

class TestExpiredToken:

    def test_expired_token_returns_invalid_200(self, client):
        """An expired token (expires_at in the past) returns 200 with status='invalid'."""
        firm = _make_firm(f"tok-exptok-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        # Forge an already-expired token row
        import secrets
        raw_token = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

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

        r = client.get(f"/intake-token/validate/{raw_token}")
        assert r.status_code == 200, f"Must be 200, not {r.status_code}"
        data = r.json()
        assert data["status"] == "invalid", (
            f"Expired token must return status='invalid', got {data['status']!r}"
        )
        assert data.get("lead_id") is None
        assert data.get("firm_id") is None

    def test_service_level_expired_token_returns_invalid_dict(self):
        """validate_intake_token service function returns invalid dict for expired token."""
        firm = _make_firm(f"tok-expsvc-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        import secrets
        raw_token = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        db = TestingSessionLocal()
        try:
            row = LeadIntakeToken(
                firm_id=firm.id,
                lead_id=lead.id,
                token_hash=token_hash,
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            )
            db.add(row)
            db.commit()

            result = validate_intake_token(db=db, raw_token=raw_token)
        finally:
            db.close()

        assert result["status"] == "invalid"


# ---------------------------------------------------------------------------
# 6. Token is NOT single-use -- remains valid after first use
# ---------------------------------------------------------------------------

class TestTokenNotSingleUse:

    def test_token_valid_on_second_request(self, client):
        """A token must remain valid after a successful validation (NOT single-use).

        This test explicitly proves the non-single-use behavior -- if single-use
        logic is accidentally copied from the unsubscribe pattern, the second
        validate call would return status='invalid' and this test would fail.
        """
        firm = _make_firm(f"tok-notsingle-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        db = TestingSessionLocal()
        try:
            raw_token = mint_intake_token(db=db, firm_id=firm.id, lead_id=lead.id)
        finally:
            db.close()

        # First validation
        r1 = client.get(f"/intake-token/validate/{raw_token}")
        assert r1.status_code == 200, r1.text
        assert r1.json()["status"] == "valid", "First validation must succeed"

        # Second validation -- must still be valid since token is NOT single-use
        r2 = client.get(f"/intake-token/validate/{raw_token}")
        assert r2.status_code == 200, r2.text
        assert r2.json()["status"] == "valid", (
            "Token must remain valid after first use -- this is explicitly NOT single-use. "
            f"Second validation returned: {r2.json()}"
        )

    def test_answer_submission_does_not_invalidate_token(self, client, firm_a_owner):
        """Submitting answers does not consume the token."""
        firm_id = uuid.UUID(firm_a_owner["firm_id"])
        lead = _make_lead(firm_id)

        db = TestingSessionLocal()
        try:
            raw_token = mint_intake_token(db=db, firm_id=firm_id, lead_id=lead.id)
        finally:
            db.close()

        # Submit answers
        r1 = client.post(
            f"/intake-token/answers/{raw_token}",
            json={
                "answers": [{"kind": "flag"}]
            },
        )
        assert r1.status_code == 200, r1.text
        assert r1.json()["status"] == "ok"

        # Token still valid for another request
        r2 = client.get(f"/intake-token/validate/{raw_token}")
        assert r2.json()["status"] == "valid", (
            "Token must remain valid after submitting answers -- "
            f"got {r2.json()['status']!r}"
        )


# ---------------------------------------------------------------------------
# 7. Rate limiting (decorator present; disabled in test env for test isolation)
# ---------------------------------------------------------------------------

class TestRateLimiting:

    def test_validate_endpoint_responds_correctly_without_rate_limit_error(self, client):
        """
        @limiter.limit('5/minute') is applied to GET /intake-token/validate/{token}.
        In tests, RATE_LIMIT_ENABLED=false so no 429 fires -- this confirms the
        endpoint works under the decorator without being incorrectly throttled.
        """
        firm = _make_firm(f"rl-val-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)

        db = TestingSessionLocal()
        try:
            raw_token = mint_intake_token(db=db, firm_id=firm.id, lead_id=lead.id)
        finally:
            db.close()

        # Call more than 5 times -- in prod this would trigger 429;
        # in tests RATE_LIMIT_ENABLED=false so all succeed.
        for _ in range(6):
            r = client.get(f"/intake-token/validate/{raw_token}")
            assert r.status_code == 200, (
                f"Rate limit must be disabled in tests. Got {r.status_code}: {r.text}"
            )

    def test_answers_endpoint_responds_correctly_without_rate_limit_error(self, client, firm_a_owner):
        """@limiter.limit('5/minute') on POST /intake-token/answers/{token} is disabled in tests."""
        firm_id = uuid.UUID(firm_a_owner["firm_id"])
        lead = _make_lead(firm_id)

        db = TestingSessionLocal()
        try:
            raw_token = mint_intake_token(db=db, firm_id=firm_id, lead_id=lead.id)
        finally:
            db.close()

        for _ in range(6):
            r = client.post(
                f"/intake-token/answers/{raw_token}",
                json={"answers": []},
            )
            assert r.status_code == 200, (
                f"Rate limit must be disabled in tests. Got {r.status_code}: {r.text}"
            )


# ---------------------------------------------------------------------------
# 8. Tenant isolation
# ---------------------------------------------------------------------------

class TestTenantIsolation:

    def test_token_from_firm_a_cannot_resolve_firm_b_data(self):
        """A Firm A token only resolves Firm A's lead_id and firm_id."""
        firm_a = _make_firm(f"iso-a-{uuid.uuid4().hex[:6]}")
        firm_b = _make_firm(f"iso-b-{uuid.uuid4().hex[:6]}")
        lead_a = _make_lead(firm_a.id)
        lead_b = _make_lead(firm_b.id)  # noqa: F841 -- created to prove isolation

        db = TestingSessionLocal()
        try:
            raw_token_a = mint_intake_token(db=db, firm_id=firm_a.id, lead_id=lead_a.id)
            result = validate_intake_token(db=db, raw_token=raw_token_a)
        finally:
            db.close()

        assert result["status"] == "valid"
        assert result["firm_id"] == str(firm_a.id), "Must resolve Firm A's firm_id"
        assert result["lead_id"] == str(lead_a.id), "Must resolve Firm A's lead_id"
        # Explicitly confirm it is not Firm B's IDs
        assert result["firm_id"] != str(firm_b.id), "Must not resolve Firm B"
        assert result["lead_id"] != str(lead_b.id), "Must not resolve Firm B's lead"

    def test_answers_written_to_correct_firm_and_lead(self, client, firm_a_owner, firm_b_owner):
        """Answers submitted via a Firm A token are scoped to Firm A's lead only."""
        firm_a_id = uuid.UUID(firm_a_owner["firm_id"])
        firm_b_id = uuid.UUID(firm_b_owner["firm_id"])
        lead_a = _make_lead(firm_a_id)
        lead_b = _make_lead(firm_b_id)  # noqa: F841

        db = TestingSessionLocal()
        try:
            raw_token_a = mint_intake_token(db=db, firm_id=firm_a_id, lead_id=lead_a.id)
        finally:
            db.close()

        r = client.post(
            f"/intake-token/answers/{raw_token_a}",
            json={
                "answers": [
                    {"kind": "flag"},
                ]
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["written"] == 1

        # Confirm the written row belongs to Firm A / Lead A only
        db2 = TestingSessionLocal()
        try:
            written = db2.query(IntakeAnswer).filter(
                IntakeAnswer.lead_id == lead_a.id,
                IntakeAnswer.firm_id == firm_a_id,
            ).all()
            assert len(written) == 1, "Exactly one answer row for Firm A's lead"

            # No rows written for Firm B
            firm_b_rows = db2.query(IntakeAnswer).filter(
                IntakeAnswer.firm_id == firm_b_id,
            ).all()
            assert len(firm_b_rows) == 0, "No rows written under Firm B"
        finally:
            db2.close()

    def test_mint_endpoint_rejects_lead_from_different_firm(self, client, firm_a_owner, firm_b_owner):
        """POST /intake-token/mint rejects a lead_id that belongs to a different firm."""
        # Create a lead under Firm B
        firm_b_id = uuid.UUID(firm_b_owner["firm_id"])
        lead_b = _make_lead(firm_b_id)

        # Authenticate as Firm A's owner and try to mint for Firm B's lead
        r = client.post(
            "/intake-token/mint",
            json={"lead_id": str(lead_b.id)},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 404, (
            f"Firm A's owner must not be able to mint a token for Firm B's lead. Got {r.status_code}: {r.text}"
        )
