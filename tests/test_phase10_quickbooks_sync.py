# tests/test_phase10_quickbooks_sync.py

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import uuid

from tests.conftest import TestingSessionLocal
from app.models.client import Client
from app.models.integration import Integration
from app.crud import integration as crud_integration
from app.services.quickbooks_service import QuickBooksService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_connected_integration(firm_id: uuid.UUID) -> Integration:
    """Create a connected QB integration with a fake realm_id."""
    db = TestingSessionLocal()
    try:
        integration = crud_integration.create_integration(db, firm_id=firm_id, provider="quickbooks")
        crud_integration.update_integration_tokens(
            db,
            integration,
            access_token="fake_access",
            refresh_token="fake_refresh",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scopes="com.intuit.quickbooks.accounting",
            external_account_id="realm-test-123",
        )
        db.refresh(integration)
        return integration
    finally:
        db.close()


def _fake_qb_customer_response(customers: list) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"QueryResponse": {"Customer": customers}}
    mock_resp.raise_for_status.return_value = None
    return mock_resp


def _fake_create_customer_response(qb_id: str) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"Customer": {"Id": qb_id}}
    mock_resp.raise_for_status.return_value = None
    return mock_resp


# ---------------------------------------------------------------------------
# Test 1 — sync_clients returns 400 if QuickBooks is not connected
# ---------------------------------------------------------------------------
def test_sync_clients_returns_400_if_not_connected(client, firm_a_owner):
    resp = client.post("/integrations/quickbooks/sync/clients", headers=firm_a_owner["headers"])
    assert resp.status_code == 400
    assert "not connected" in resp.json()["detail"].lower()


def test_sync_clients_returns_400_if_integration_exists_but_disconnected(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    db = TestingSessionLocal()
    try:
        crud_integration.create_integration(db, firm_id=firm_id, provider="quickbooks")
    finally:
        db.close()

    resp = client.post("/integrations/quickbooks/sync/clients", headers=firm_a_owner["headers"])
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Test 2 — import_clients_from_quickbooks creates new Client records
# ---------------------------------------------------------------------------
def test_import_creates_new_clients(firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    integration = _make_connected_integration(firm_id)

    customers = [
        {"Id": "1", "DisplayName": "Acme Corp", "PrimaryEmailAddr": {"Address": "acme@example.com"}, "Active": True},
        {"Id": "2", "DisplayName": "Globex Inc", "Active": True},
    ]

    svc = QuickBooksService()
    db = TestingSessionLocal()
    try:
        with patch("requests.get", return_value=_fake_qb_customer_response(customers)):
            # Patch get_access_token so we don't need real tokens
            with patch.object(svc, "get_access_token", return_value="fake_access"):
                result = svc.import_clients_from_quickbooks(integration, db, firm_id)

        assert result["imported"] == 2
        assert result["updated"] == 0
        assert result["skipped"] == 0

        from sqlalchemy import select
        stmt = select(Client).where(Client.firm_id == firm_id)
        clients = list(db.execute(stmt).scalars().all())
        assert len(clients) == 2
        names = {c.name for c in clients}
        assert "Acme Corp" in names
        assert "Globex Inc" in names
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 3 — import skips existing clients matched by email, sets quickbooks_customer_id
# ---------------------------------------------------------------------------
def test_import_updates_existing_client_by_email(firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    integration = _make_connected_integration(firm_id)

    db = TestingSessionLocal()
    try:
        # Pre-create a client with matching email but no QB ID
        existing = Client(firm_id=firm_id, name="Existing Client", email="existing@example.com")
        db.add(existing)
        db.commit()
        db.refresh(existing)
        existing_id = existing.id
    finally:
        db.close()

    customers = [
        {"Id": "QB-99", "DisplayName": "Existing Client QB", "PrimaryEmailAddr": {"Address": "existing@example.com"}, "Active": True},
    ]

    svc = QuickBooksService()
    db = TestingSessionLocal()
    try:
        with patch("requests.get", return_value=_fake_qb_customer_response(customers)):
            with patch.object(svc, "get_access_token", return_value="fake_access"):
                result = svc.import_clients_from_quickbooks(integration, db, firm_id)

        assert result["imported"] == 0
        assert result["updated"] == 1
        assert result["skipped"] == 0

        from sqlalchemy import select
        stmt = select(Client).where(Client.id == existing_id)
        client = db.execute(stmt).scalar_one()
        assert client.quickbooks_customer_id == "QB-99"
        # Name should NOT be overwritten
        assert client.name == "Existing Client"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 4 — export_client_to_quickbooks skips clients that already have qb ID
# ---------------------------------------------------------------------------
def test_export_skips_client_already_linked(firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    integration = _make_connected_integration(firm_id)

    db = TestingSessionLocal()
    try:
        client_obj = Client(
            firm_id=firm_id,
            name="Already Linked",
            email="linked@example.com",
            quickbooks_customer_id="EXISTING-QB-ID",
        )
        db.add(client_obj)
        db.commit()
        db.refresh(client_obj)

        svc = QuickBooksService()
        with patch("requests.post") as mock_post:
            with patch.object(svc, "get_access_token", return_value="fake_access"):
                result = svc.export_client_to_quickbooks(integration, db, client_obj)
            mock_post.assert_not_called()

        assert result == "EXISTING-QB-ID"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 5 — export_client_to_quickbooks creates new QB customer and saves ID
# ---------------------------------------------------------------------------
def test_export_creates_new_qb_customer(firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    integration = _make_connected_integration(firm_id)

    db = TestingSessionLocal()
    try:
        client_obj = Client(firm_id=firm_id, name="New Client", email="newclient@example.com")
        db.add(client_obj)
        db.commit()
        db.refresh(client_obj)
        client_id = client_obj.id

        svc = QuickBooksService()
        with patch("requests.post", return_value=_fake_create_customer_response("QB-NEW-42")):
            with patch.object(svc, "get_access_token", return_value="fake_access"):
                result = svc.export_client_to_quickbooks(integration, db, client_obj)

        assert result == "QB-NEW-42"

        from sqlalchemy import select
        stmt = select(Client).where(Client.id == client_id)
        refreshed = db.execute(stmt).scalar_one()
        assert refreshed.quickbooks_customer_id == "QB-NEW-42"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 6 — sync_clients calls both import and export and returns combined counts
# ---------------------------------------------------------------------------
def test_sync_clients_combined_result(firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    integration = _make_connected_integration(firm_id)

    # One unlinked client to be exported
    db = TestingSessionLocal()
    try:
        unlinked = Client(firm_id=firm_id, name="Unlinked Client", email="unlinked@example.com")
        db.add(unlinked)
        db.commit()
    finally:
        db.close()

    # QB returns one new customer
    customers = [
        {"Id": "QB-100", "DisplayName": "QB Customer", "PrimaryEmailAddr": {"Address": "qb@example.com"}, "Active": True},
    ]

    svc = QuickBooksService()
    db = TestingSessionLocal()
    try:
        with patch("requests.get", return_value=_fake_qb_customer_response(customers)):
            with patch("requests.post", return_value=_fake_create_customer_response("QB-EXPORT-1")):
                with patch.object(svc, "get_access_token", return_value="fake_access"):
                    result = svc.sync_clients(integration, db, firm_id)

        assert result["imported"] == 1      # QB-100 imported
        assert result["exported"] == 1      # Unlinked client exported
        assert "updated" in result
        assert "skipped" in result
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 7 — Tenant isolation: sync only affects clients belonging to correct firm
# ---------------------------------------------------------------------------
def test_sync_tenant_isolation(firm_a_owner, firm_b_owner):
    firm_a_id = uuid.UUID(firm_a_owner["firm_id"])
    firm_b_id = uuid.UUID(firm_b_owner["firm_id"])

    # Create an integration for firm A only
    integration = _make_connected_integration(firm_a_id)

    customers = [
        {"Id": "QB-FIRM-A", "DisplayName": "Firm A Customer", "Active": True},
    ]

    svc = QuickBooksService()
    db = TestingSessionLocal()
    try:
        with patch("requests.get", return_value=_fake_qb_customer_response(customers)):
            with patch.object(svc, "get_access_token", return_value="fake_access"):
                result = svc.import_clients_from_quickbooks(integration, db, firm_a_id)

        assert result["imported"] == 1

        # Firm B should have zero clients
        from sqlalchemy import select
        stmt = select(Client).where(Client.firm_id == firm_b_id)
        firm_b_clients = list(db.execute(stmt).scalars().all())
        assert len(firm_b_clients) == 0
    finally:
        db.close()
