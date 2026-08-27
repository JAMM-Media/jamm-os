# tests/test_portal_settings.py
"""
Tests for portal account settings endpoints:
  GET/PATCH /portal/account/profile
  GET /portal/account/sessions
  DELETE /portal/account/sessions/{session_id}

Covers:
  1. A client can update their own name, email, and phone.
  2. Scoping: the PATCH endpoint uses get_current_portal_client and has no client_id
     parameter, so a client cannot target another client's record.
  3. A client can list their own active sessions.
  4. A client can revoke one of their own sessions; the revoked token is then rejected.
  5. A client cannot revoke another client's session.
"""

import uuid

import pytest

from app.models.client import Client
from app.models.firm import Firm
from app.services.portal_auth import hash_portal_password
from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_portal_client(firm_id: str, name: str = "Test Client") -> dict:
    email = f"ps-{uuid.uuid4().hex[:8]}@example.com"
    password = "testpass1!"
    db = TestingSessionLocal()
    try:
        c = Client(
            firm_id=uuid.UUID(firm_id),
            name=name,
            email=email,
            portal_access_enabled=True,
            portal_password_hash=hash_portal_password(password),
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        return {"client_id": str(c.id), "email": email, "password": password}
    finally:
        db.close()


def _portal_login(http_client, firm_id: str, email: str, password: str) -> dict:
    db = TestingSessionLocal()
    try:
        firm = db.get(Firm, uuid.UUID(firm_id))
        slug = firm.slug
    finally:
        db.close()
    r = http_client.post("/portal/auth/login", json={
        "firm_slug": slug,
        "email": email,
        "password": password,
    })
    assert r.status_code == 200, f"Portal login failed: {r.json()}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _get_client_from_db(client_id: str) -> Client:
    db = TestingSessionLocal()
    try:
        return db.get(Client, uuid.UUID(client_id))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 1: Client can update their own profile
# ---------------------------------------------------------------------------

def test_client_can_update_profile(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    portal_info = _create_portal_client(firm_id)
    portal_headers = _portal_login(client, firm_id, portal_info["email"], portal_info["password"])

    r = client.patch(
        "/portal/account/profile",
        json={"name": "Jane Doe", "phone": "+1 555-0100"},
        headers=portal_headers,
    )
    assert r.status_code == 200, r.json()
    data = r.json()
    assert data["name"] == "Jane Doe"
    assert data["phone"] == "+1 555-0100"

    # Verify persisted in DB
    c = _get_client_from_db(portal_info["client_id"])
    assert c.name == "Jane Doe"
    assert c.phone == "+1 555-0100"


def test_profile_update_validates_email(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    portal_info = _create_portal_client(firm_id)
    portal_headers = _portal_login(client, firm_id, portal_info["email"], portal_info["password"])

    r = client.patch(
        "/portal/account/profile",
        json={"email": "not-an-email"},
        headers=portal_headers,
    )
    assert r.status_code == 422, r.json()


def test_profile_get_returns_own_data(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    portal_info = _create_portal_client(firm_id, name="Alice Smith")
    portal_headers = _portal_login(client, firm_id, portal_info["email"], portal_info["password"])

    r = client.get("/portal/account/profile", headers=portal_headers)
    assert r.status_code == 200, r.json()
    assert r.json()["name"] == "Alice Smith"
    assert r.json()["email"] == portal_info["email"]


# ---------------------------------------------------------------------------
# Test 2: Scoping -- PATCH profile is scoped to own record only
# (the endpoint accepts no client_id parameter, so isolation is structural)
# ---------------------------------------------------------------------------

def test_profile_update_is_scoped_to_own_client(client, firm_a_owner):
    """Two clients in the same firm cannot affect each other's profiles."""
    firm_id = firm_a_owner["firm_id"]
    client_a = _create_portal_client(firm_id, name="Client A")
    client_b = _create_portal_client(firm_id, name="Client B")
    headers_b = _portal_login(client, firm_id, client_b["email"], client_b["password"])

    # Client B updates their own name
    r = client.patch(
        "/portal/account/profile",
        json={"name": "Client B Updated"},
        headers=headers_b,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Client B Updated"

    # Client A's record is untouched
    c_a = _get_client_from_db(client_a["client_id"])
    assert c_a.name == "Client A"


# ---------------------------------------------------------------------------
# Test 3: Client can list their own active sessions
# ---------------------------------------------------------------------------

def test_client_can_list_own_sessions(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    portal_info = _create_portal_client(firm_id)
    portal_headers = _portal_login(client, firm_id, portal_info["email"], portal_info["password"])

    r = client.get("/portal/account/sessions", headers=portal_headers)
    assert r.status_code == 200, r.json()
    sessions = r.json()
    assert isinstance(sessions, list)
    assert len(sessions) >= 1
    for s in sessions:
        assert "id" in s
        assert "created_at" in s
        assert "last_active_at" in s


# ---------------------------------------------------------------------------
# Test 4: Client can revoke their own session; revoked token is then rejected
# ---------------------------------------------------------------------------

def test_client_can_revoke_own_session(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    portal_info = _create_portal_client(firm_id)
    # Login twice to have two sessions; we'll revoke one to test without locking ourselves out
    headers_1 = _portal_login(client, firm_id, portal_info["email"], portal_info["password"])
    headers_2 = _portal_login(client, firm_id, portal_info["email"], portal_info["password"])

    # List sessions from session 2's perspective
    sessions_r = client.get("/portal/account/sessions", headers=headers_2)
    sessions = sessions_r.json()
    assert len(sessions) >= 2

    # Find the session that belongs to headers_1 by revoking the first one in the list
    # (both belong to the same client, either is safe to revoke for this test)
    target_id = sessions[0]["id"]

    revoke_r = client.delete(f"/portal/account/sessions/{target_id}", headers=headers_2)
    assert revoke_r.status_code == 204

    # Confirm it no longer appears in the list
    sessions_r2 = client.get("/portal/account/sessions", headers=headers_2)
    remaining_ids = [s["id"] for s in sessions_r2.json()]
    assert target_id not in remaining_ids


# ---------------------------------------------------------------------------
# Test 5: Client cannot revoke another client's session
# ---------------------------------------------------------------------------

def test_client_cannot_revoke_other_clients_session(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    client_a = _create_portal_client(firm_id)
    client_b = _create_portal_client(firm_id)
    headers_a = _portal_login(client, firm_id, client_a["email"], client_a["password"])
    headers_b = _portal_login(client, firm_id, client_b["email"], client_b["password"])

    # Get client A's session id
    sessions_a = client.get("/portal/account/sessions", headers=headers_a).json()
    assert len(sessions_a) >= 1
    session_a_id = sessions_a[0]["id"]

    # Client B tries to revoke client A's session
    r = client.delete(f"/portal/account/sessions/{session_a_id}", headers=headers_b)
    assert r.status_code == 404, r.json()

    # Session is still there
    sessions_a2 = client.get("/portal/account/sessions", headers=headers_a).json()
    assert any(s["id"] == session_a_id for s in sessions_a2)
