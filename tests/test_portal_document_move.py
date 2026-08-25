# tests/test_portal_document_move.py
"""
Tests for PATCH /portal/documents/{document_id}/move.

Covers:
  1. A client can move their own document into their own folder.
  2. A client can move a document back to root (folder_id = null).
  3. A client cannot move a document into a folder belonging to a different client.
  4. A client cannot move another client's document.
  5. A real audit log entry is created on a successful move.
"""

import uuid

import pytest

from app.models.client import Client
from app.models.document import Document, DocumentAuditLog
from app.models.firm import Firm
from app.services.portal_auth import hash_portal_password
from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_portal_client(firm_id: str) -> dict:
    email = f"portal-move-{uuid.uuid4().hex[:8]}@example.com"
    password = "testpass1!"
    db = TestingSessionLocal()
    try:
        c = Client(
            firm_id=uuid.UUID(firm_id),
            name="Portal Move Client",
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


def _insert_document(firm_id: str, client_id: str, folder_id=None) -> str:
    db = TestingSessionLocal()
    try:
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
        return str(doc.id)
    finally:
        db.close()


def _create_folder(http_client, staff_headers: dict, firm_id: str, client_id: str, name="Test Folder") -> str:
    r = http_client.post("/folders/", json={"name": name, "client_id": client_id}, headers=staff_headers)
    assert r.status_code == 201, r.json()
    return r.json()["id"]


def _get_doc_folder_id(doc_id: str):
    db = TestingSessionLocal()
    try:
        doc = db.get(Document, uuid.UUID(doc_id))
        return str(doc.folder_id) if doc.folder_id else None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 1: Client can move their own document into their own folder
# ---------------------------------------------------------------------------

def test_client_can_move_document_into_own_folder(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    staff_headers = firm_a_owner["headers"]

    portal_info = _create_portal_client(firm_id)
    portal_headers = _portal_login(client, firm_id, portal_info["email"], portal_info["password"])

    doc_id = _insert_document(firm_id, portal_info["client_id"])
    folder_id = _create_folder(client, staff_headers, firm_id, portal_info["client_id"])

    r = client.patch(
        f"/portal/documents/{doc_id}/move",
        json={"folder_id": folder_id},
        headers=portal_headers,
    )
    assert r.status_code == 200, r.json()
    assert r.json()["folder_id"] == folder_id
    assert _get_doc_folder_id(doc_id) == folder_id


# ---------------------------------------------------------------------------
# Test 2: Client can move a document back to root (folder_id = null)
# ---------------------------------------------------------------------------

def test_client_can_move_document_to_root(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    staff_headers = firm_a_owner["headers"]

    portal_info = _create_portal_client(firm_id)
    portal_headers = _portal_login(client, firm_id, portal_info["email"], portal_info["password"])

    folder_id = _create_folder(client, staff_headers, firm_id, portal_info["client_id"])
    doc_id = _insert_document(firm_id, portal_info["client_id"], folder_id=folder_id)

    r = client.patch(
        f"/portal/documents/{doc_id}/move",
        json={"folder_id": None},
        headers=portal_headers,
    )
    assert r.status_code == 200, r.json()
    assert r.json()["folder_id"] is None
    assert _get_doc_folder_id(doc_id) is None


# ---------------------------------------------------------------------------
# Test 3: Client cannot move a document into a folder belonging to a different client
# ---------------------------------------------------------------------------

def test_client_cannot_move_into_other_clients_folder(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    staff_headers = firm_a_owner["headers"]

    portal_a = _create_portal_client(firm_id)
    portal_b = _create_portal_client(firm_id)
    portal_a_headers = _portal_login(client, firm_id, portal_a["email"], portal_a["password"])

    doc_id = _insert_document(firm_id, portal_a["client_id"])
    # Folder belongs to client B, not client A
    other_folder_id = _create_folder(client, staff_headers, firm_id, portal_b["client_id"], name="B Folder")

    r = client.patch(
        f"/portal/documents/{doc_id}/move",
        json={"folder_id": other_folder_id},
        headers=portal_a_headers,
    )
    assert r.status_code == 404, r.json()


# ---------------------------------------------------------------------------
# Test 4: Client cannot move another client's document
# ---------------------------------------------------------------------------

def test_client_cannot_move_other_clients_document(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    staff_headers = firm_a_owner["headers"]

    portal_a = _create_portal_client(firm_id)
    portal_b = _create_portal_client(firm_id)
    portal_b_headers = _portal_login(client, firm_id, portal_b["email"], portal_b["password"])

    # Document belongs to client A
    doc_id = _insert_document(firm_id, portal_a["client_id"])
    folder_id = _create_folder(client, staff_headers, firm_id, portal_b["client_id"])

    # Client B tries to move client A's document
    r = client.patch(
        f"/portal/documents/{doc_id}/move",
        json={"folder_id": folder_id},
        headers=portal_b_headers,
    )
    assert r.status_code == 404, r.json()
    # Confirm document was not moved
    assert _get_doc_folder_id(doc_id) is None


# ---------------------------------------------------------------------------
# Test 5: Audit log entry is created on a successful move
# ---------------------------------------------------------------------------

def test_move_creates_audit_log_entry(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    staff_headers = firm_a_owner["headers"]

    portal_info = _create_portal_client(firm_id)
    portal_headers = _portal_login(client, firm_id, portal_info["email"], portal_info["password"])

    doc_id = _insert_document(firm_id, portal_info["client_id"])
    folder_id = _create_folder(client, staff_headers, firm_id, portal_info["client_id"])

    r = client.patch(
        f"/portal/documents/{doc_id}/move",
        json={"folder_id": folder_id},
        headers=portal_headers,
    )
    assert r.status_code == 200, r.json()

    db = TestingSessionLocal()
    try:
        log = (
            db.query(DocumentAuditLog)
            .filter(
                DocumentAuditLog.document_id == uuid.UUID(doc_id),
                DocumentAuditLog.action == "portal_move",
            )
            .first()
        )
        assert log is not None, "No audit log entry found for the move"
        assert str(log.firm_id) == firm_id
    finally:
        db.close()
