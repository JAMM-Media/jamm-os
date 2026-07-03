# tests/test_phase11e_firm_chat.py

"""
Phase 11E — Firm Chat: Internal Team Communication

Tests cover:
 - Channel CRUD (create, rename, delete, list)
 - RBAC enforcement (only firm_owner can create/rename/delete channels)
 - Duplicate channel name rejection (409)
 - Channel name normalization (lowercase, spaces→hyphens)
 - Message sending and retrieval (oldest first)
 - @mention storage
 - Unread count tracking per channel
 - Unread count clearing on message fetch
 - Aggregate unread summary
 - Tenant isolation (Firm 2 cannot access Firm 1 channels)
 - client_portal_user JWT rejected on all firm chat endpoints
"""

import uuid

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.user import User
from app.models.client import Client
from app.core.security import get_password_hash
from app.core.enums import UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_firm(name: str, slug: str) -> Firm:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=name, slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)
        return firm
    finally:
        db.close()


def _create_user(firm_id: uuid.UUID, email: str, role: UserRole,
                 full_name: str = "Test User", password: str = "pass1234") -> User:
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=email,
            hashed_password=get_password_hash(password),
            full_name=full_name,
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def _create_portal_client(firm_id: uuid.UUID, slug: str) -> dict:
    """Create a Client with portal access enabled and return login credentials."""
    from app.services.portal_auth import hash_portal_password
    db = TestingSessionLocal()
    try:
        email = f"portal-{uuid.uuid4().hex[:6]}@example.com"
        password = "portalpass1"
        c = Client(
            firm_id=firm_id,
            name="Portal Client",
            email=email,
            portal_password_hash=hash_portal_password(password),
            portal_access_enabled=True,
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        return {"email": email, "password": password, "firm_slug": slug}
    finally:
        db.close()


def _login(http_client, email: str, password: str = "pass1234") -> dict:
    r = http_client.post("/auth/token", json={"username": email, "password": password})
    assert r.status_code == 200, f"Login failed for {email}: {r.text}"
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
    One firm with firm_owner, manager_user, staff_user.
    A second firm for tenant isolation.
    """
    uid = uuid.uuid4().hex[:6]

    # Firm 1
    firm1 = _create_firm(f"Chat Firm 1 {uid}", f"chat-firm1-{uid}")
    owner = _create_user(firm1.id, f"owner-{uid}@f1.com", UserRole.firm_owner,
                         full_name="Owner One")
    manager = _create_user(firm1.id, f"mgr-{uid}@f1.com", UserRole.manager,
                           full_name="Manager One")
    staff = _create_user(firm1.id, f"staff-{uid}@f1.com", UserRole.staff,
                         full_name="Staff One")

    # Firm 2 (for tenant isolation)
    firm2 = _create_firm(f"Chat Firm 2 {uid}", f"chat-firm2-{uid}")
    owner2 = _create_user(firm2.id, f"owner2-{uid}@f2.com", UserRole.firm_owner,
                          full_name="Owner Two")

    # Portal client for firm1 (for client_portal_user forbidden test)
    portal_creds = _create_portal_client(firm1.id, f"chat-firm1-{uid}")

    owner_headers = _login(http_client, f"owner-{uid}@f1.com")
    manager_headers = _login(http_client, f"mgr-{uid}@f1.com")
    staff_headers = _login(http_client, f"staff-{uid}@f1.com")
    owner2_headers = _login(http_client, f"owner2-{uid}@f2.com")
    portal_headers = _login_portal(
        http_client, portal_creds["firm_slug"],
        portal_creds["email"], portal_creds["password"]
    )

    return {
        "firm1_id": firm1.id,
        "firm2_id": firm2.id,
        "owner_id": owner.id,
        "manager_id": manager.id,
        "staff_id": staff.id,
        "owner_headers": owner_headers,
        "manager_headers": manager_headers,
        "staff_headers": staff_headers,
        "owner2_headers": owner2_headers,
        "portal_headers": portal_headers,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_create_channel_firm_owner(client):
    """firm_owner creates a channel — 201 with correct fields."""
    ctx = _setup(client)

    r = client.post(
        "/firm-chat/channels",
        json={"name": "general"},
        headers=ctx["owner_headers"],
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["name"] == "general"
    assert data["is_deleted"] is False
    assert data["unread_count"] == 0


def test_create_channel_manager_forbidden(client):
    """manager cannot create a channel — 403."""
    ctx = _setup(client)

    r = client.post(
        "/firm-chat/channels",
        json={"name": "manager-channel"},
        headers=ctx["manager_headers"],
    )
    assert r.status_code == 403, r.text


def test_create_channel_staff_forbidden(client):
    """staff cannot create a channel — 403."""
    ctx = _setup(client)

    r = client.post(
        "/firm-chat/channels",
        json={"name": "staff-channel"},
        headers=ctx["staff_headers"],
    )
    assert r.status_code == 403, r.text


def test_create_channel_duplicate_name(client):
    """Creating a channel with an existing name returns 409."""
    ctx = _setup(client)

    client.post(
        "/firm-chat/channels",
        json={"name": "duplicate"},
        headers=ctx["owner_headers"],
    )
    r = client.post(
        "/firm-chat/channels",
        json={"name": "duplicate"},
        headers=ctx["owner_headers"],
    )
    assert r.status_code == 409, r.text


def test_create_channel_name_normalized(client):
    """Channel name with uppercase and spaces is normalized to lowercase-with-hyphens."""
    ctx = _setup(client)

    r = client.post(
        "/firm-chat/channels",
        json={"name": "Tax Returns 2025"},
        headers=ctx["owner_headers"],
    )
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "tax-returns-2025"


def test_rename_channel(client):
    """firm_owner renames a channel — new name returned."""
    ctx = _setup(client)

    create_r = client.post(
        "/firm-chat/channels",
        json={"name": "old-name"},
        headers=ctx["owner_headers"],
    )
    assert create_r.status_code == 201
    channel_id = create_r.json()["id"]

    r = client.patch(
        f"/firm-chat/channels/{channel_id}",
        json={"name": "new-name"},
        headers=ctx["owner_headers"],
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "new-name"


def test_delete_channel(client):
    """firm_owner deletes a channel — it no longer appears in GET /channels."""
    ctx = _setup(client)

    create_r = client.post(
        "/firm-chat/channels",
        json={"name": "to-delete"},
        headers=ctx["owner_headers"],
    )
    assert create_r.status_code == 201
    channel_id = create_r.json()["id"]

    del_r = client.delete(
        f"/firm-chat/channels/{channel_id}",
        headers=ctx["owner_headers"],
    )
    assert del_r.status_code == 204, del_r.text

    list_r = client.get("/firm-chat/channels", headers=ctx["owner_headers"])
    assert list_r.status_code == 200
    channel_ids = [ch["id"] for ch in list_r.json()]
    assert channel_id not in channel_ids


def test_send_message(client):
    """Staff sends a message to a channel — 201 with correct fields."""
    ctx = _setup(client)

    create_r = client.post(
        "/firm-chat/channels",
        json={"name": "general"},
        headers=ctx["owner_headers"],
    )
    channel_id = create_r.json()["id"]

    r = client.post(
        f"/firm-chat/channels/{channel_id}/messages",
        json={"body": "Hello team!", "mentions": []},
        headers=ctx["staff_headers"],
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["body"] == "Hello team!"
    assert data["channel_id"] == channel_id
    assert data["is_deleted"] is False
    assert data["sender_name"] == "Staff One"


def test_send_message_with_mention(client):
    """Message with mentions stores mention UUIDs correctly."""
    ctx = _setup(client)

    create_r = client.post(
        "/firm-chat/channels",
        json={"name": "mentions-test"},
        headers=ctx["owner_headers"],
    )
    channel_id = create_r.json()["id"]

    manager_id = str(ctx["manager_id"])
    r = client.post(
        f"/firm-chat/channels/{channel_id}/messages",
        json={
            "body": "Hey @manager!",
            "mentions": [manager_id],
        },
        headers=ctx["staff_headers"],
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert manager_id in data["mentions"]


def test_get_messages(client):
    """Messages are returned oldest first."""
    ctx = _setup(client)

    create_r = client.post(
        "/firm-chat/channels",
        json={"name": "ordering-test"},
        headers=ctx["owner_headers"],
    )
    channel_id = create_r.json()["id"]

    client.post(
        f"/firm-chat/channels/{channel_id}/messages",
        json={"body": "First message", "mentions": []},
        headers=ctx["staff_headers"],
    )
    client.post(
        f"/firm-chat/channels/{channel_id}/messages",
        json={"body": "Second message", "mentions": []},
        headers=ctx["manager_headers"],
    )

    r = client.get(
        f"/firm-chat/channels/{channel_id}/messages",
        headers=ctx["owner_headers"],
    )
    assert r.status_code == 200, r.text
    messages = r.json()
    assert len(messages) == 2
    assert messages[0]["body"] == "First message"
    assert messages[1]["body"] == "Second message"


def test_unread_count_increments(client):
    """After staff sends a message, manager's unread count for that channel is 1."""
    ctx = _setup(client)

    create_r = client.post(
        "/firm-chat/channels",
        json={"name": "unread-test"},
        headers=ctx["owner_headers"],
    )
    channel_id = create_r.json()["id"]

    # Staff sends a message
    client.post(
        f"/firm-chat/channels/{channel_id}/messages",
        json={"body": "Unread message", "mentions": []},
        headers=ctx["staff_headers"],
    )

    # Check manager's unread count via the channel list
    r = client.get("/firm-chat/channels", headers=ctx["manager_headers"])
    assert r.status_code == 200, r.text
    channels = r.json()
    ch = next((c for c in channels if c["id"] == channel_id), None)
    assert ch is not None
    assert ch["unread_count"] == 1


def test_unread_count_clears_on_read(client):
    """manager fetches messages, their unread count drops to 0."""
    ctx = _setup(client)

    create_r = client.post(
        "/firm-chat/channels",
        json={"name": "read-clear-test"},
        headers=ctx["owner_headers"],
    )
    channel_id = create_r.json()["id"]

    # Staff sends a message
    client.post(
        f"/firm-chat/channels/{channel_id}/messages",
        data={"body": "Message to read", "mentions": "[]"},
        headers=ctx["staff_headers"],
    )

    # Manager fetches messages — marks as read
    client.get(
        f"/firm-chat/channels/{channel_id}/messages",
        headers=ctx["manager_headers"],
    )

    # Check unread count is now 0 for manager
    r = client.get("/firm-chat/channels", headers=ctx["manager_headers"])
    channels = r.json()
    ch = next((c for c in channels if c["id"] == channel_id), None)
    assert ch is not None
    assert ch["unread_count"] == 0


def test_get_unread_summary(client):
    """GET /firm-chat/unread returns correct total and per_channel breakdown."""
    ctx = _setup(client)

    # Create two channels
    ch1_r = client.post(
        "/firm-chat/channels",
        json={"name": "channel-one"},
        headers=ctx["owner_headers"],
    )
    ch1_id = ch1_r.json()["id"]

    ch2_r = client.post(
        "/firm-chat/channels",
        json={"name": "channel-two"},
        headers=ctx["owner_headers"],
    )
    ch2_id = ch2_r.json()["id"]

    # Staff sends 1 message to channel 1 and 2 messages to channel 2
    client.post(
        f"/firm-chat/channels/{ch1_id}/messages",
        json={"body": "Msg in ch1", "mentions": []},
        headers=ctx["staff_headers"],
    )
    client.post(
        f"/firm-chat/channels/{ch2_id}/messages",
        json={"body": "Msg 1 in ch2", "mentions": []},
        headers=ctx["staff_headers"],
    )
    client.post(
        f"/firm-chat/channels/{ch2_id}/messages",
        json={"body": "Msg 2 in ch2", "mentions": []},
        headers=ctx["staff_headers"],
    )

    # Manager checks unread summary
    r = client.get("/firm-chat/unread", headers=ctx["manager_headers"])
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total_unread"] == 3
    assert data["per_channel"][ch1_id] == 1
    assert data["per_channel"][ch2_id] == 2


def test_tenant_isolation(client):
    """firm2 owner cannot access firm1 channels."""
    ctx = _setup(client)

    # firm1 owner creates a channel
    client.post(
        "/firm-chat/channels",
        json={"name": "firm1-secret"},
        headers=ctx["owner_headers"],
    )

    # firm2 owner lists channels — should see none of firm1's channels
    r = client.get("/firm-chat/channels", headers=ctx["owner2_headers"])
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_client_portal_user_forbidden(client):
    """A client_portal_user JWT is rejected on any firm chat endpoint."""
    ctx = _setup(client)

    r = client.get("/firm-chat/channels", headers=ctx["portal_headers"])
    assert r.status_code in (401, 403), r.text
