# tests/test_phase11b_notes.py

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

def _create_firm_with_owner(name: str, slug: str, email: str, password: str = "pass1234") -> dict:
    """Create a firm + firm_owner in the DB; return (firm_id, user_id) UUIDs."""
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

        return {"firm_id": firm.id, "user_id": user.id, "email": email, "password": password}
    finally:
        db.close()


def _create_staff_in_firm(firm_id: uuid.UUID, email: str, full_name: str = "Staff User",
                           password: str = "staffpass") -> dict:
    """Create a staff user in an existing firm."""
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


def _create_manager_in_firm(firm_id: uuid.UUID, email: str, password: str = "mgrpass") -> dict:
    """Create a manager user in an existing firm."""
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=email,
            hashed_password=get_password_hash(password),
            full_name="Manager User",
            role=UserRole.manager,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"user_id": user.id, "email": email, "password": password}
    finally:
        db.close()


def _create_client_in_firm(firm_id: uuid.UUID) -> uuid.UUID:
    """Create a client in the given firm; return client_id."""
    db = TestingSessionLocal()
    try:
        client = Client(
            firm_id=firm_id,
            name=f"Test Client {uuid.uuid4().hex[:6]}",
            email=f"client-{uuid.uuid4().hex[:6]}@example.com",
        )
        db.add(client)
        db.commit()
        db.refresh(client)
        return client.id
    finally:
        db.close()


def _login(http_client, email: str, password: str) -> dict:
    """Return auth headers for the given credentials."""
    r = http_client.post("/auth/token", json={"username": email, "password": password})
    assert r.status_code == 200, f"Login failed: {r.text}"
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Setup shared across tests (inline, not fixtures, per codebase pattern)
# ---------------------------------------------------------------------------

def _setup_two_firms(http_client):
    """Create two firms, two users per firm (owner + staff), one client per firm."""
    # Firm A
    firm_a = _create_firm_with_owner("Notes Firm A", f"notes-firm-a-{uuid.uuid4().hex[:6]}",
                                     f"owner-a-{uuid.uuid4().hex[:6]}@firma.com")
    staff_a = _create_staff_in_firm(firm_a["firm_id"],
                                    f"staff-a-{uuid.uuid4().hex[:6]}@firma.com",
                                    full_name="Staff Alpha")
    client_a_id = _create_client_in_firm(firm_a["firm_id"])

    # Firm B
    firm_b = _create_firm_with_owner("Notes Firm B", f"notes-firm-b-{uuid.uuid4().hex[:6]}",
                                     f"owner-b-{uuid.uuid4().hex[:6]}@firmb.com")
    staff_b = _create_staff_in_firm(firm_b["firm_id"],
                                    f"staff-b-{uuid.uuid4().hex[:6]}@firmb.com",
                                    full_name="Staff Beta")
    client_b_id = _create_client_in_firm(firm_b["firm_id"])

    # Auth headers
    owner_a_headers = _login(http_client, firm_a["email"], firm_a["password"])
    staff_a_headers = _login(http_client, staff_a["email"], staff_a["password"])
    owner_b_headers = _login(http_client, firm_b["email"], firm_b["password"])
    staff_b_headers = _login(http_client, staff_b["email"], staff_b["password"])

    return {
        "firm_a_id": firm_a["firm_id"],
        "firm_b_id": firm_b["firm_id"],
        "owner_a_headers": owner_a_headers,
        "staff_a_headers": staff_a_headers,
        "owner_b_headers": owner_b_headers,
        "staff_b_headers": staff_b_headers,
        "client_a_id": client_a_id,
        "client_b_id": client_b_id,
        "staff_a_info": staff_a,
        "staff_b_info": staff_b,
        "firm_a_info": firm_a,
        "firm_b_info": firm_b,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_create_note_success(client):
    """Staff creates a shared note on a client."""
    ctx = _setup_two_firms(client)
    entity_id = str(ctx["client_a_id"])

    r = client.post(
        "/notes/",
        json={"body": "Meeting with client about taxes.", "is_private": False,
              "entity_type": "client", "entity_id": entity_id},
        headers=ctx["staff_a_headers"],
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["body"] == "Meeting with client about taxes."
    assert data["is_private"] is False
    assert data["entity_type"] == "client"
    assert data["entity_id"] == entity_id


def test_create_note_private(client):
    """Staff creates a private note."""
    ctx = _setup_two_firms(client)
    entity_id = str(ctx["client_a_id"])

    r = client.post(
        "/notes/",
        json={"body": "Private observation.", "is_private": True,
              "entity_type": "client", "entity_id": entity_id},
        headers=ctx["staff_a_headers"],
    )
    assert r.status_code == 201, r.text
    assert r.json()["is_private"] is True


def test_get_notes_shared(client):
    """Another staff member can see shared notes."""
    ctx = _setup_two_firms(client)
    entity_id = str(ctx["client_a_id"])

    # Staff A creates a shared note
    r_create = client.post(
        "/notes/",
        json={"body": "Shared note visible to all.", "is_private": False,
              "entity_type": "client", "entity_id": entity_id},
        headers=ctx["staff_a_headers"],
    )
    assert r_create.status_code == 201

    # Second staff user in same firm (owner_a can see it too)
    r_get = client.get(
        "/notes/",
        params={"entity_type": "client", "entity_id": entity_id},
        headers=ctx["owner_a_headers"],
    )
    assert r_get.status_code == 200
    notes = r_get.json()
    assert len(notes) == 1
    assert notes[0]["body"] == "Shared note visible to all."


def test_get_notes_private_hidden(client):
    """Staff A's private note is hidden from owner_a (another user)."""
    ctx = _setup_two_firms(client)
    entity_id = str(ctx["client_a_id"])

    # Staff A creates a private note
    client.post(
        "/notes/",
        json={"body": "Private — only staff A should see.", "is_private": True,
              "entity_type": "client", "entity_id": entity_id},
        headers=ctx["staff_a_headers"],
    )

    # Owner A (different user) should NOT see it
    r = client.get(
        "/notes/",
        params={"entity_type": "client", "entity_id": entity_id},
        headers=ctx["owner_a_headers"],
    )
    assert r.status_code == 200
    assert r.json() == []


def test_get_notes_private_visible_to_author(client):
    """Author can see their own private note."""
    ctx = _setup_two_firms(client)
    entity_id = str(ctx["client_a_id"])

    client.post(
        "/notes/",
        json={"body": "My private note.", "is_private": True,
              "entity_type": "client", "entity_id": entity_id},
        headers=ctx["staff_a_headers"],
    )

    r = client.get(
        "/notes/",
        params={"entity_type": "client", "entity_id": entity_id},
        headers=ctx["staff_a_headers"],
    )
    assert r.status_code == 200
    notes = r.json()
    assert len(notes) == 1
    assert notes[0]["body"] == "My private note."


def test_update_note_success(client):
    """Author can update the body of their own note."""
    ctx = _setup_two_firms(client)
    entity_id = str(ctx["client_a_id"])

    r_create = client.post(
        "/notes/",
        json={"body": "Original body.", "is_private": False,
              "entity_type": "client", "entity_id": entity_id},
        headers=ctx["staff_a_headers"],
    )
    note_id = r_create.json()["id"]

    r_update = client.patch(
        f"/notes/{note_id}",
        json={"body": "Updated body."},
        headers=ctx["staff_a_headers"],
    )
    assert r_update.status_code == 200, r_update.text
    assert r_update.json()["body"] == "Updated body."


def test_update_note_forbidden(client):
    """Non-author cannot update note — must get 403."""
    ctx = _setup_two_firms(client)
    entity_id = str(ctx["client_a_id"])

    r_create = client.post(
        "/notes/",
        json={"body": "Staff A's note.", "is_private": False,
              "entity_type": "client", "entity_id": entity_id},
        headers=ctx["staff_a_headers"],
    )
    note_id = r_create.json()["id"]

    # Owner A tries to update — should be 403
    r_update = client.patch(
        f"/notes/{note_id}",
        json={"body": "Tampering with someone else's note."},
        headers=ctx["owner_a_headers"],
    )
    assert r_update.status_code == 403, r_update.text


def test_delete_note_own(client):
    """Staff can delete their own note."""
    ctx = _setup_two_firms(client)
    entity_id = str(ctx["client_a_id"])

    r_create = client.post(
        "/notes/",
        json={"body": "I will delete this.", "is_private": False,
              "entity_type": "client", "entity_id": entity_id},
        headers=ctx["staff_a_headers"],
    )
    note_id = r_create.json()["id"]

    r_del = client.delete(f"/notes/{note_id}", headers=ctx["staff_a_headers"])
    assert r_del.status_code == 204, r_del.text

    # Note should no longer be visible
    r_get = client.get(
        "/notes/",
        params={"entity_type": "client", "entity_id": entity_id},
        headers=ctx["staff_a_headers"],
    )
    assert r_get.json() == []


def test_delete_note_other_staff_forbidden(client):
    """Staff cannot delete another staff member's note — 403."""
    ctx = _setup_two_firms(client)
    firm_id = ctx["firm_a_id"]
    entity_id = str(ctx["client_a_id"])

    # Create a second staff user in Firm A
    staff_a2 = _create_staff_in_firm(firm_id, f"staff-a2-{uuid.uuid4().hex[:6]}@firma.com")
    staff_a2_headers = _login(client, staff_a2["email"], staff_a2["password"])

    # Staff A creates a note
    r_create = client.post(
        "/notes/",
        json={"body": "Staff A's note.", "is_private": False,
              "entity_type": "client", "entity_id": entity_id},
        headers=ctx["staff_a_headers"],
    )
    note_id = r_create.json()["id"]

    # Staff A2 tries to delete — should be 403
    r_del = client.delete(f"/notes/{note_id}", headers=staff_a2_headers)
    assert r_del.status_code == 403, r_del.text


def test_delete_note_manager_can_delete_any(client):
    """Manager can delete another user's note."""
    ctx = _setup_two_firms(client)
    firm_id = ctx["firm_a_id"]
    entity_id = str(ctx["client_a_id"])

    # Create a manager in Firm A
    mgr = _create_manager_in_firm(firm_id, f"mgr-a-{uuid.uuid4().hex[:6]}@firma.com")
    mgr_headers = _login(client, mgr["email"], mgr["password"])

    # Staff A creates a note
    r_create = client.post(
        "/notes/",
        json={"body": "Staff note that manager will delete.", "is_private": False,
              "entity_type": "client", "entity_id": entity_id},
        headers=ctx["staff_a_headers"],
    )
    note_id = r_create.json()["id"]

    # Manager deletes it — should succeed
    r_del = client.delete(f"/notes/{note_id}", headers=mgr_headers)
    assert r_del.status_code == 204, r_del.text


def test_invalid_entity_type(client):
    """POST with entity_type='invoice' returns 400."""
    ctx = _setup_two_firms(client)
    entity_id = str(ctx["client_a_id"])

    r = client.post(
        "/notes/",
        json={"body": "This should fail.", "is_private": False,
              "entity_type": "invoice", "entity_id": entity_id},
        headers=ctx["staff_a_headers"],
    )
    assert r.status_code == 400, r.text


def test_tenant_isolation(client):
    """Firm A staff cannot read Firm B notes via Firm A token."""
    ctx = _setup_two_firms(client)
    client_b_id = str(ctx["client_b_id"])

    # Firm B staff creates a note on their own client
    client.post(
        "/notes/",
        json={"body": "Firm B confidential note.", "is_private": False,
              "entity_type": "client", "entity_id": client_b_id},
        headers=ctx["staff_b_headers"],
    )

    # Firm A staff tries to GET notes for Firm B's client_id using Firm A's token.
    # The server should scope queries to Firm A's firm_id — so the result must be empty.
    r = client.get(
        "/notes/",
        params={"entity_type": "client", "entity_id": client_b_id},
        headers=ctx["staff_a_headers"],
    )
    assert r.status_code == 200
    # Firm A's note query is scoped to firm_a — must not return Firm B's notes
    assert r.json() == []
