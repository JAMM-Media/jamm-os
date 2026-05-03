# tests/test_phase10_quickbooks_oauth.py

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import uuid

from tests.conftest import TestingSessionLocal
from app.crud import integration as crud_integration
from app.services.quickbooks_service import QuickBooksService


FAKE_TOKEN_RESPONSE = {
    "access_token": "fake_access",
    "refresh_token": "fake_refresh",
    "expires_in": 3600,
}


def _mock_post_success(*args, **kwargs):
    mock_resp = MagicMock()
    mock_resp.json.return_value = FAKE_TOKEN_RESPONSE
    mock_resp.raise_for_status.return_value = None
    return mock_resp


# ---------------------------------------------------------------------------
# Test 1 — GET /integrations/quickbooks/connect returns valid authorization_url
# ---------------------------------------------------------------------------
def test_quickbooks_connect_returns_authorization_url(client, firm_a_owner):
    resp = client.get("/integrations/quickbooks/connect", headers=firm_a_owner["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert "authorization_url" in data
    assert data["authorization_url"].startswith("https://appcenter.intuit.com")


# ---------------------------------------------------------------------------
# Test 2 — Connecting when integration already exists is idempotent
# ---------------------------------------------------------------------------
def test_quickbooks_connect_idempotent(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    db = TestingSessionLocal()
    try:
        crud_integration.create_integration(db, firm_id=firm_id, provider="quickbooks")
    finally:
        db.close()

    resp = client.get("/integrations/quickbooks/connect", headers=firm_a_owner["headers"])
    assert resp.status_code == 200
    assert resp.json()["authorization_url"].startswith("https://appcenter.intuit.com")

    # Only one record should exist
    db = TestingSessionLocal()
    try:
        integrations = crud_integration.get_integrations_for_firm(db, firm_id=firm_id)
        assert len(integrations) == 1
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 3 — Callback with missing/invalid code returns 400
# ---------------------------------------------------------------------------
def test_quickbooks_callback_invalid_code_returns_400(client):
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("invalid_grant")
        mock_post.return_value = mock_resp

        # state must be a valid UUID for firm lookup — use a random one
        state = str(uuid.uuid4())
        resp = client.get(
            f"/integrations/quickbooks/callback?code=bad_code&realmId=12345&state={state}"
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Test 4 — Successful mocked callback sets status=connected and stores realm_id
# ---------------------------------------------------------------------------
def test_quickbooks_callback_success(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]

    # Create integration so callback can find it
    db = TestingSessionLocal()
    try:
        crud_integration.create_integration(db, firm_id=uuid.UUID(firm_id), provider="quickbooks")
    finally:
        db.close()

    with patch("requests.post", side_effect=_mock_post_success):
        resp = client.get(
            f"/integrations/quickbooks/callback?code=auth_code_xyz&realmId=realm-123&state={firm_id}"
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "connected"

    db = TestingSessionLocal()
    try:
        integration = crud_integration.get_integration(
            db, firm_id=uuid.UUID(firm_id), provider="quickbooks"
        )
        assert integration is not None
        assert integration.status == "connected"
        assert integration.external_account_id == "realm-123"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 5 — Token refresh skips when token is not expiring soon
# ---------------------------------------------------------------------------
def test_token_refresh_skips_when_not_expiring(firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    db = TestingSessionLocal()
    try:
        integration = crud_integration.create_integration(db, firm_id=firm_id, provider="quickbooks")
        crud_integration.update_integration_tokens(
            db,
            integration,
            access_token="original_access",
            refresh_token="original_refresh",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scopes="com.intuit.quickbooks.accounting",
            external_account_id="realm-abc",
        )
        db.refresh(integration)

        svc = QuickBooksService()
        with patch("requests.post") as mock_post:
            result = svc.refresh_tokens_if_needed(integration, db)
            # requests.post should NOT have been called
            mock_post.assert_not_called()

        assert result.encrypted_access_token == integration.encrypted_access_token
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 6 — Token refresh fires when token expires within 5 minutes
# ---------------------------------------------------------------------------
def test_token_refresh_fires_when_expiring_soon(firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    db = TestingSessionLocal()
    try:
        integration = crud_integration.create_integration(db, firm_id=firm_id, provider="quickbooks")
        crud_integration.update_integration_tokens(
            db,
            integration,
            access_token="original_access",
            refresh_token="original_refresh",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=2),  # within 5 min
            scopes="com.intuit.quickbooks.accounting",
            external_account_id="realm-abc",
        )
        db.refresh(integration)

        svc = QuickBooksService()
        with patch("requests.post", side_effect=_mock_post_success):
            result = svc.refresh_tokens_if_needed(integration, db)

        assert result.status == "connected"
        # Access token should have been updated (re-encrypted from "fake_access")
        from app.services.token_encryption import decrypt_token
        assert decrypt_token(result.encrypted_access_token) == "fake_access"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 7 — DELETE /integrations/quickbooks sets status to disconnected
# ---------------------------------------------------------------------------
def test_delete_quickbooks_integration(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])

    # Connect first via mocked callback
    db = TestingSessionLocal()
    try:
        integration = crud_integration.create_integration(db, firm_id=firm_id, provider="quickbooks")
        crud_integration.update_integration_tokens(
            db,
            integration,
            access_token="tok",
            refresh_token="ref",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scopes=None,
            external_account_id="realm-xyz",
        )
    finally:
        db.close()

    resp = client.delete("/integrations/quickbooks", headers=firm_a_owner["headers"])
    assert resp.status_code == 204

    db = TestingSessionLocal()
    try:
        integration = crud_integration.get_integration(db, firm_id=firm_id, provider="quickbooks")
        assert integration.status == "disconnected"
        assert integration.encrypted_access_token is None
        assert integration.encrypted_refresh_token is None
    finally:
        db.close()
