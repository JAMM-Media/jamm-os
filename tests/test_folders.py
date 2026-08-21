# tests/test_folders.py
"""
Tests for the folder CRUD endpoints and portal folder visibility.

Covers:
  1. Manager/firm_owner can create a folder for a client in their firm.
  2. Staff from a different firm cannot create or list folders belonging to another firm.
  3. Portal client can list their own folders; cannot see another client's folders.
  4. Portal client cannot create, rename, or delete folders (no such endpoints).
  5. A document assigned to a folder is returned when filtering by that folder_id,
     and excluded from a different folder's filter.
  6. Deleting a folder moves its documents to root (folder_id = NULL).
"""

import uuid

import pytest

from app.models.client import Client
from app.models.document import Document
from app.services.portal_auth import hash_portal_password
from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_client(firm_id: str) -> str:
    """Insert a plain (non-portal) client and return its id as a string."""
    db = TestingSessionLocal()
    try:
        c = Client(
            firm_id=uuid.UUID(firm_id),
            name=f"Client-{uuid.uuid4().hex[:6]}",
            email=f"c-{uuid.uuid4().hex[:8]}@example.com",
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        return str(c.id)
    finally:
        db.close()


def _create_portal_client(firm_id: str) -> dict:
    """Insert a portal-enabled client. Returns {client_id, email, password}."""
    email = f"portal-{uuid.uuid4().hex[:8]}@example.com"
    password = "testpass1!"
    db = TestingSessionLocal()
    try:
        c = Client(
            firm_id=uuid.UUID(firm_id),
            name="Portal Client",
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
    from app.models.firm import Firm
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


def _insert_document(db, firm_id: str, client_id: str, folder_id=None) -> Document:
    doc = Document(
        firm_id=uuid.UUID(firm_id),
        client_id=uuid.UUID(client_id),
        uploaded_by=None,
        filename="test.pdf",
        s3_key=f"test/{uuid.uuid4()}/test.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        visibility="client_visible",
        folder_id=uuid.UUID(folder_id) if folder_id else None,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# ---------------------------------------------------------------------------
# Test 1: Manager can create a folder for a client in their firm
# ---------------------------------------------------------------------------

def test_manager_can_create_folder(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    headers = firm_a_owner["headers"]
    client_id = _create_client(firm_id)

    r = client.post("/folders/", json={
        "name": "Tax Documents 2024",
        "client_id": client_id,
    }, headers=headers)
    assert r.status_code == 201, r.json()
    data = r.json()
    assert data["name"] == "Tax Documents 2024"
    assert data["client_id"] == client_id
    assert data["firm_id"] == firm_id
    assert data["parent_folder_id"] is None


def test_manager_can_list_folders(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    headers = firm_a_owner["headers"]
    client_id = _create_client(firm_id)

    client.post("/folders/", json={"name": "Folder A", "client_id": client_id}, headers=headers)
    client.post("/folders/", json={"name": "Folder B", "client_id": client_id}, headers=headers)

    r = client.get(f"/folders/?client_id={client_id}", headers=headers)
    assert r.status_code == 200
    names = [f["name"] for f in r.json()]
    assert "Folder A" in names
    assert "Folder B" in names


def test_manager_can_rename_folder(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    headers = firm_a_owner["headers"]
    client_id = _create_client(firm_id)

    create_r = client.post("/folders/", json={"name": "Old Name", "client_id": client_id}, headers=headers)
    folder_id = create_r.json()["id"]

    patch_r = client.patch(f"/folders/{folder_id}", json={"name": "New Name"}, headers=headers)
    assert patch_r.status_code == 200
    assert patch_r.json()["name"] == "New Name"


def test_manager_can_delete_folder(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    headers = firm_a_owner["headers"]
    client_id = _create_client(firm_id)

    create_r = client.post("/folders/", json={"name": "To Delete", "client_id": client_id}, headers=headers)
    folder_id = create_r.json()["id"]

    del_r = client.delete(f"/folders/{folder_id}", headers=headers)
    assert del_r.status_code == 204

    list_r = client.get(f"/folders/?client_id={client_id}", headers=headers)
    assert not any(f["id"] == folder_id for f in list_r.json())


# ---------------------------------------------------------------------------
# Test 2: Cross-firm tenant isolation
# ---------------------------------------------------------------------------

def test_firm_b_cannot_see_firm_a_folders(client, firm_a_owner, firm_b_owner):
    firm_a_id = firm_a_owner["firm_id"]
    firm_b_headers = firm_b_owner["headers"]
    client_id = _create_client(firm_a_id)

    r = client.post("/folders/", json={"name": "Firm A Private", "client_id": client_id},
                    headers=firm_a_owner["headers"])
    assert r.status_code == 201
    folder_id = r.json()["id"]

    # Firm B tries to list or fetch directly
    list_r = client.get(f"/folders/?client_id={client_id}", headers=firm_b_headers)
    # Either returns empty or 404 -- must not return Firm A's folder
    if list_r.status_code == 200:
        assert not any(f["id"] == folder_id for f in list_r.json())

    patch_r = client.patch(f"/folders/{folder_id}", json={"name": "Hijacked"}, headers=firm_b_headers)
    assert patch_r.status_code == 404

    del_r = client.delete(f"/folders/{folder_id}", headers=firm_b_headers)
    assert del_r.status_code == 404


# ---------------------------------------------------------------------------
# Test 3: Portal client sees only their own firm's folders
# ---------------------------------------------------------------------------

def test_portal_client_sees_own_folders(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    staff_headers = firm_a_owner["headers"]

    portal_info = _create_portal_client(firm_id)
    other_client_id = _create_client(firm_id)
    portal_headers = _portal_login(client, firm_id, portal_info["email"], portal_info["password"])

    # Staff creates a folder for the portal client and one for another client
    own_r = client.post("/folders/", json={"name": "My Folder", "client_id": portal_info["client_id"]},
                        headers=staff_headers)
    assert own_r.status_code == 201
    own_folder_id = own_r.json()["id"]

    other_r = client.post("/folders/", json={"name": "Other Client Folder", "client_id": other_client_id},
                          headers=staff_headers)
    assert other_r.status_code == 201
    other_folder_id = other_r.json()["id"]

    r = client.get("/portal/folders", headers=portal_headers)
    assert r.status_code == 200
    folder_ids = [f["id"] for f in r.json()]
    assert own_folder_id in folder_ids
    assert other_folder_id not in folder_ids


# ---------------------------------------------------------------------------
# Test 4: Portal client has no create/rename/delete folder endpoints
# ---------------------------------------------------------------------------

def test_portal_client_cannot_create_rename_or_delete_folders(client, firm_a_owner):
    """Confirm the portal router has no folder-management endpoints."""
    firm_id = firm_a_owner["firm_id"]
    portal_info = _create_portal_client(firm_id)
    portal_headers = _portal_login(client, firm_id, portal_info["email"], portal_info["password"])

    # POST to staff endpoint should be rejected (not a portal route)
    r = client.post("/folders/", json={"name": "X", "client_id": portal_info["client_id"]},
                    headers=portal_headers)
    assert r.status_code in (401, 403, 422), r.status_code

    # PATCH to staff endpoint should be rejected
    fake_id = str(uuid.uuid4())
    r = client.patch(f"/folders/{fake_id}", json={"name": "X"}, headers=portal_headers)
    assert r.status_code in (401, 403, 404, 422), r.status_code

    # DELETE to staff endpoint should be rejected
    r = client.delete(f"/folders/{fake_id}", headers=portal_headers)
    assert r.status_code in (401, 403, 404, 422), r.status_code


# ---------------------------------------------------------------------------
# Test 5: Document assigned to a folder is returned by the folder filter
# ---------------------------------------------------------------------------

def test_portal_documents_folder_filter(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    staff_headers = firm_a_owner["headers"]
    portal_info = _create_portal_client(firm_id)
    portal_headers = _portal_login(client, firm_id, portal_info["email"], portal_info["password"])
    client_id = portal_info["client_id"]

    # Create two folders
    folder_a_id = client.post("/folders/", json={"name": "Folder A", "client_id": client_id},
                               headers=staff_headers).json()["id"]
    folder_b_id = client.post("/folders/", json={"name": "Folder B", "client_id": client_id},
                               headers=staff_headers).json()["id"]

    db = TestingSessionLocal()
    try:
        doc_in_a = _insert_document(db, firm_id, client_id, folder_id=folder_a_id)
        doc_at_root = _insert_document(db, firm_id, client_id, folder_id=None)
        doc_in_a_id = str(doc_in_a.id)
        doc_at_root_id = str(doc_at_root.id)
    finally:
        db.close()

    # Filter by folder A
    r = client.get(f"/portal/documents?folder_id={folder_a_id}", headers=portal_headers)
    assert r.status_code == 200
    ids_in_a = [d["id"] for d in r.json()]
    assert doc_in_a_id in ids_in_a
    assert doc_at_root_id not in ids_in_a

    # Filter by folder B (no docs)
    r = client.get(f"/portal/documents?folder_id={folder_b_id}", headers=portal_headers)
    assert r.status_code == 200
    assert r.json() == []

    # No filter: all visible docs returned
    r = client.get("/portal/documents", headers=portal_headers)
    assert r.status_code == 200
    all_ids = [d["id"] for d in r.json()]
    assert doc_in_a_id in all_ids
    assert doc_at_root_id in all_ids


# ---------------------------------------------------------------------------
# Test 6: Deleting a folder moves its documents to root (folder_id = NULL)
# ---------------------------------------------------------------------------

def test_delete_folder_moves_documents_to_root(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    staff_headers = firm_a_owner["headers"]
    client_id = _create_client(firm_id)

    folder_id = client.post("/folders/", json={"name": "Temp", "client_id": client_id},
                             headers=staff_headers).json()["id"]

    db = TestingSessionLocal()
    try:
        doc = _insert_document(db, firm_id, client_id, folder_id=folder_id)
        doc_id = doc.id
    finally:
        db.close()

    # Delete the folder
    r = client.delete(f"/folders/{folder_id}", headers=staff_headers)
    assert r.status_code == 204

    # Document must still exist with folder_id = NULL
    db = TestingSessionLocal()
    try:
        refreshed = db.get(Document, doc_id)
        assert refreshed is not None, "Document was deleted when folder was deleted -- should have been preserved"
        assert refreshed.folder_id is None, f"folder_id should be NULL after folder deletion, got {refreshed.folder_id}"
    finally:
        db.close()
