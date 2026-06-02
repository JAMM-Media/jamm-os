# tests/test_phase10_integrations.py

import pytest
from tests.conftest import TestingSessionLocal
from app.models.integration import Integration
from app.crud import integration as crud_integration
from app.services.token_encryption import encrypt_token, decrypt_token
import uuid


# ---------------------------------------------------------------------------
# Test 1 — List integrations returns empty list for a new firm
# ---------------------------------------------------------------------------
def test_list_integrations_empty(client, firm_a_owner):
    resp = client.get("/integrations/", headers=firm_a_owner["headers"])
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Test 2 — Create integration via CRUD, confirm it appears in GET /integrations/
# ---------------------------------------------------------------------------
def test_create_integration_via_crud_appears_in_list(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    db = TestingSessionLocal()
    try:
        crud_integration.create_integration(db, firm_id=firm_id, provider="quickbooks")
    finally:
        db.close()

    resp = client.get("/integrations/", headers=firm_a_owner["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["provider"] == "quickbooks"
    assert data[0]["status"] == "disconnected"


# ---------------------------------------------------------------------------
# Test 3 — GET /integrations/{provider} returns 404 for unknown provider
# ---------------------------------------------------------------------------
def test_get_integration_unknown_provider_returns_404(client, firm_a_owner):
    resp = client.get("/integrations/nonexistent", headers=firm_a_owner["headers"])
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 4 — Token encryption round-trip
# ---------------------------------------------------------------------------
def test_token_encryption_round_trip():
    original = "super-secret-access-token-abc123"
    ciphertext = encrypt_token(original)
    assert ciphertext != original
    assert decrypt_token(ciphertext) == original


# ---------------------------------------------------------------------------
# Test 5 — Encrypted tokens are NOT present in IntegrationOut API response
# ---------------------------------------------------------------------------
def test_tokens_not_exposed_in_api_response(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    db = TestingSessionLocal()
    try:
        integration = crud_integration.create_integration(db, firm_id=firm_id, provider="quickbooks")
        crud_integration.update_integration_tokens(
            db,
            integration,
            access_token="my-access-token",
            refresh_token="my-refresh-token",
            expires_at=None,
            scopes="com.intuit.quickbooks.accounting",
            external_account_id="realm-abc",
        )
    finally:
        db.close()

    resp = client.get("/integrations/quickbooks", headers=firm_a_owner["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert "encrypted_access_token" not in body
    assert "encrypted_refresh_token" not in body
    # Confirm useful fields are present
    assert body["provider"] == "quickbooks"
    assert body["status"] == "connected"
    assert body["external_account_id"] == "realm-abc"


# ---------------------------------------------------------------------------
# Test 6 — DELETE /integrations/{provider} sets status to disconnected + clears tokens
# ---------------------------------------------------------------------------
def test_delete_integration_disconnects_and_clears_tokens(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    db = TestingSessionLocal()
    try:
        integration = crud_integration.create_integration(db, firm_id=firm_id, provider="quickbooks")
        crud_integration.update_integration_tokens(
            db,
            integration,
            access_token="token",
            refresh_token="refresh",
            expires_at=None,
            scopes=None,
            external_account_id=None,
        )
    finally:
        db.close()

    resp = client.delete("/integrations/quickbooks", headers=firm_a_owner["headers"])
    assert resp.status_code == 204

    # Verify DB state directly
    db = TestingSessionLocal()
    try:
        from sqlalchemy import select
        stmt = select(Integration).where(
            Integration.firm_id == firm_id,
            Integration.provider == "quickbooks",
        )
        record = db.execute(stmt).scalar_one_or_none()
        assert record is not None
        assert record.status == "disconnected"
        assert record.encrypted_access_token is None
        assert record.encrypted_refresh_token is None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 7 — Tenant isolation: Firm A cannot see Firm B's integrations
# ---------------------------------------------------------------------------
def test_tenant_isolation(client, firm_a_owner, firm_b_owner):
    firm_b_id = uuid.UUID(firm_b_owner["firm_id"])

    # Create an integration for Firm B directly via CRUD
    db = TestingSessionLocal()
    try:
        crud_integration.create_integration(db, firm_id=firm_b_id, provider="quickbooks")
    finally:
        db.close()

    # Firm A's list should be empty
    resp = client.get("/integrations/", headers=firm_a_owner["headers"])
    assert resp.status_code == 200
    assert resp.json() == []

    # Firm A cannot GET Firm B's integration by provider either
    resp = client.get("/integrations/quickbooks", headers=firm_a_owner["headers"])
    assert resp.status_code == 404
