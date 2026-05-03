# tests/test_phase11c_messages.py

"""
Phase 11C — Client Messaging System test suite.

Tests cover:
 - Staff sending messages to clients
 - Portal clients sending messages
 - Message thread retrieval (both sides)
 - Unread count tracking and clearing on read
 - Tenant isolation (Firm A cannot read Firm B messages)
 - Scope enforcement (staff JWT rejected on portal endpoint, portal JWT rejected on staff endpoint)
"""

import uuid

from tests.conftest import TestingSessionLocal
from app.models.client import Client
from app.models.firm import Firm
from app.models.user import User
from app.core.security import get_password_hash
from app.core.enums import UserRole
from app.services.portal_auth import hash_portal_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_firm_with_owner(name: str, slug: str, email: str, password: str = "pass1234") -> dict:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=name, slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)

        user = User(
            firm_id=firm.id,
            email=email,
            hashed_password=get_password_hash(password),
            full_name="Owner User",
            role=UserRole.firm_owner,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        return {
            "firm_id": firm.id,
            "firm_slug": firm.slug,
            "user_id": user.id,
            "email": email,
            "password": password,
        }
    finally:
        db.close()


def _create_staff_in_firm(firm_id: uuid.UUID, email: str, full_name: str = "Staff User",
                           password: str = "staffpass") -> dict:
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=email,
            hashed_password=get_password_hash(password),
            full_name=full_name,
            role=UserRole.staff,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"user_id": user.id, "email": email, "password": password}
    finally:
        db.close()


def _create_client_with_portal(
    firm_id: uuid.UUID,
    name: str = "Test Client",
    portal_email: str = None,
    portal_password: str = "clientpass1",
) -> dict:
    """Create a client with portal access enabled. Returns client_id + login info."""
    db = TestingSessionLocal()
    try:
        email = portal_email or f"portal-{uuid.uuid4().hex[:6]}@example.com"
        client = Client(
            firm_id=firm_id,
            name=name,
            email=email,
            portal_password_hash=hash_portal_password(portal_password),
            portal_access_enabled=True,
        )
        db.add(client)
        db.commit()
        db.refresh(client)
        return {
            "client_id": client.id,
            "email": email,
            "password": portal_password,
        }
    finally:
        db.close()


def _login_staff(http_client, email: str, password: str) -> dict:
    r = http_client.post("/auth/token", json={"username": email, "password": password})
    assert r.status_code == 200, f"Staff login failed: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _login_portal(http_client, firm_slug: str, email: str, password: str) -> dict:
    r = http_client.post("/portal/auth/login", json={
        "email": email,
        "firm_slug": firm_slug,
        "password": password,
    })
    assert r.status_code == 200, f"Portal login failed: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup(http_client) -> dict:
    """
    Two firms, two staff per firm (owner + staff), one client per firm with portal access.
    """
    uid = uuid.uuid4().hex[:6]

    # Firm A
    firm_a = _create_firm_with_owner(
        f"Msg Firm A {uid}", f"msg-firm-a-{uid}",
        f"owner-a-{uid}@firma.com",
    )
    staff_a = _create_staff_in_firm(firm_a["firm_id"], f"staff-a-{uid}@firma.com",
                                     full_name="Staff Alpha")
    client_a = _create_client_with_portal(firm_a["firm_id"],
                                           name="Client Alpha",
                                           portal_email=f"client-a-{uid}@example.com")

    # Firm B
    firm_b = _create_firm_with_owner(
        f"Msg Firm B {uid}", f"msg-firm-b-{uid}",
        f"owner-b-{uid}@firmb.com",
    )
    staff_b = _create_staff_in_firm(firm_b["firm_id"], f"staff-b-{uid}@firmb.com",
                                     full_name="Staff Beta")
    client_b = _create_client_with_portal(firm_b["firm_id"],
                                           name="Client Beta",
                                           portal_email=f"client-b-{uid}@example.com")

    owner_a_headers = _login_staff(http_client, firm_a["email"], firm_a["password"])
    staff_a_headers = _login_staff(http_client, staff_a["email"], staff_a["password"])
    owner_b_headers = _login_staff(http_client, firm_b["email"], firm_b["password"])
    portal_a_headers = _login_portal(http_client, firm_a["firm_slug"],
                                      client_a["email"], client_a["password"])
    portal_b_headers = _login_portal(http_client, firm_b["firm_slug"],
                                      client_b["email"], client_b["password"])

    return {
        "firm_a_id": firm_a["firm_id"],
        "firm_b_id": firm_b["firm_id"],
        "client_a_id": client_a["client_id"],
        "client_b_id": client_b["client_id"],
        "owner_a_headers": owner_a_headers,
        "staff_a_headers": staff_a_headers,
        "owner_b_headers": owner_b_headers,
        "portal_a_headers": portal_a_headers,
        "portal_b_headers": portal_b_headers,
        "staff_a_info": staff_a,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_staff_send_message(client):
    """Staff sends a message to a client — 201 returned with correct body."""
    ctx = _setup(client)
    client_id = str(ctx["client_a_id"])

    r = client.post(
        f"/clients/{client_id}/messages",
        json={"body": "Hello from staff"},
        headers=ctx["staff_a_headers"],
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["body"] == "Hello from staff"
    assert data["sender_role"] == "staff"
    assert data["client_id"] == client_id
    assert data["is_deleted"] is False


def test_client_send_message(client):
    """Portal user sends a message via portal endpoint — 201 returned."""
    ctx = _setup(client)
    client_id = str(ctx["client_a_id"])

    r = client.post(
        f"/portal/clients/{client_id}/messages",
        json={"body": "Hello from client portal"},
        headers=ctx["portal_a_headers"],
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["body"] == "Hello from client portal"
    assert data["sender_role"] == "client"
    assert data["sender_id"] is None


def test_get_messages_staff(client):
    """Staff fetches message thread — sees both staff and client messages in order."""
    ctx = _setup(client)
    client_id = str(ctx["client_a_id"])

    # Staff sends first
    client.post(
        f"/clients/{client_id}/messages",
        json={"body": "Staff message 1"},
        headers=ctx["staff_a_headers"],
    )
    # Client sends second
    client.post(
        f"/portal/clients/{client_id}/messages",
        json={"body": "Client reply"},
        headers=ctx["portal_a_headers"],
    )

    r = client.get(
        f"/clients/{client_id}/messages",
        headers=ctx["owner_a_headers"],
    )
    assert r.status_code == 200, r.text
    messages = r.json()
    assert len(messages) == 2
    assert messages[0]["body"] == "Staff message 1"
    assert messages[0]["sender_role"] == "staff"
    assert messages[1]["body"] == "Client reply"
    assert messages[1]["sender_role"] == "client"


def test_get_messages_portal(client):
    """Portal user fetches message thread — sees staff messages."""
    ctx = _setup(client)
    client_id = str(ctx["client_a_id"])

    client.post(
        f"/clients/{client_id}/messages",
        json={"body": "Staff to client"},
        headers=ctx["staff_a_headers"],
    )

    r = client.get(
        f"/portal/clients/{client_id}/messages",
        headers=ctx["portal_a_headers"],
    )
    assert r.status_code == 200, r.text
    messages = r.json()
    assert len(messages) == 1
    assert messages[0]["body"] == "Staff to client"


def test_unread_count_staff(client):
    """After client sends a message, staff unread count is 1."""
    ctx = _setup(client)
    client_id = str(ctx["client_a_id"])

    # Client sends a message
    client.post(
        f"/portal/clients/{client_id}/messages",
        json={"body": "Client says hello"},
        headers=ctx["portal_a_headers"],
    )

    r = client.get(
        f"/clients/{client_id}/messages/unread-count",
        headers=ctx["staff_a_headers"],
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["unread_count"] == 1
    assert data["client_id"] == client_id


def test_unread_count_clears_on_read(client):
    """Staff fetches messages, unread count drops to 0."""
    ctx = _setup(client)
    client_id = str(ctx["client_a_id"])

    # Client sends a message
    client.post(
        f"/portal/clients/{client_id}/messages",
        json={"body": "Client message"},
        headers=ctx["portal_a_headers"],
    )

    # Staff reads the thread (marks as read)
    client.get(
        f"/clients/{client_id}/messages",
        headers=ctx["staff_a_headers"],
    )

    # Unread count should now be 0
    r = client.get(
        f"/clients/{client_id}/messages/unread-count",
        headers=ctx["staff_a_headers"],
    )
    assert r.status_code == 200, r.text
    assert r.json()["unread_count"] == 0


def test_unread_count_portal(client):
    """After staff sends a message, portal unread count is 1."""
    ctx = _setup(client)
    client_id = str(ctx["client_a_id"])

    # Staff sends a message
    client.post(
        f"/clients/{client_id}/messages",
        json={"body": "Staff message to client"},
        headers=ctx["staff_a_headers"],
    )

    r = client.get(
        f"/portal/clients/{client_id}/messages/unread-count",
        headers=ctx["portal_a_headers"],
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["unread_count"] == 1


def test_unread_count_portal_clears_on_read(client):
    """Portal user fetches messages, portal unread count drops to 0."""
    ctx = _setup(client)
    client_id = str(ctx["client_a_id"])

    # Staff sends a message
    client.post(
        f"/clients/{client_id}/messages",
        json={"body": "Staff message"},
        headers=ctx["staff_a_headers"],
    )

    # Portal user fetches messages (marks as read)
    client.get(
        f"/portal/clients/{client_id}/messages",
        headers=ctx["portal_a_headers"],
    )

    # Portal unread count should now be 0
    r = client.get(
        f"/portal/clients/{client_id}/messages/unread-count",
        headers=ctx["portal_a_headers"],
    )
    assert r.status_code == 200, r.text
    assert r.json()["unread_count"] == 0


def test_tenant_isolation_staff(client):
    """Firm A staff cannot read Firm B client messages."""
    ctx = _setup(client)
    client_b_id = str(ctx["client_b_id"])

    # Firm B client sends a message (via portal)
    client.post(
        f"/portal/clients/{client_b_id}/messages",
        json={"body": "Firm B confidential message"},
        headers=ctx["portal_b_headers"],
    )

    # Firm A staff tries to read Firm B's messages — must get 404 (client not found in Firm A)
    r = client.get(
        f"/clients/{client_b_id}/messages",
        headers=ctx["staff_a_headers"],
    )
    # The service validates that client belongs to the firm from the token.
    # Staff endpoint scopes to firm_id from JWT — Firm B's client won't be found in Firm A
    # So we should get 200 with empty list or 404
    assert r.status_code in (200, 404), r.text
    if r.status_code == 200:
        # Must be empty — Firm A cannot see Firm B messages
        assert r.json() == []


def test_tenant_isolation_portal(client):
    """Firm A portal user cannot read Firm B client messages."""
    ctx = _setup(client)
    client_b_id = str(ctx["client_b_id"])

    # Firm B sends a message
    client.post(
        f"/clients/{client_b_id}/messages",
        json={"body": "Firm B message"},
        headers=ctx["owner_b_headers"],
    )

    # Firm A portal user tries to access Firm B client_id — must be rejected
    r = client.get(
        f"/portal/clients/{client_b_id}/messages",
        headers=ctx["portal_a_headers"],
    )
    # client_b_id != portal user's own client_id → 403
    assert r.status_code == 403, r.text


def test_staff_cannot_access_portal_endpoint(client):
    """Staff JWT rejected on portal endpoint."""
    ctx = _setup(client)
    client_a_id = str(ctx["client_a_id"])

    r = client.get(
        f"/portal/clients/{client_a_id}/messages",
        headers=ctx["staff_a_headers"],
    )
    # Portal endpoint requires portal JWT — staff JWT must be rejected
    assert r.status_code in (401, 403), r.text


def test_portal_user_cannot_access_staff_endpoint(client):
    """Portal JWT rejected on staff endpoint."""
    ctx = _setup(client)
    client_a_id = str(ctx["client_a_id"])

    r = client.get(
        f"/clients/{client_a_id}/messages",
        headers=ctx["portal_a_headers"],
    )
    # Staff endpoint requires staff JWT — portal JWT must be rejected
    assert r.status_code in (401, 403), r.text
