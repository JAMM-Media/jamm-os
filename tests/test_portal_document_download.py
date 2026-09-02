# tests/test_portal_document_download.py
"""
Tests for GET /portal/documents/{document_id}/download.

Covers:
  1. Authenticated client retrieves a real signed URL for their own document.
  2. A client cannot retrieve a signed URL for another client's document (404).
  3. The returned payload has expires_in_seconds = PRESIGNED_URL_EXPIRY (3600 seconds).
"""

import uuid
from unittest.mock import patch

from app.models.client import Client
from app.models.document import Document
from app.models.firm import Firm
from app.services.portal_auth import hash_portal_password
from app.services.s3 import PRESIGNED_URL_EXPIRY
from tests.conftest import TestingSessionLocal

# Stable fake URL used by all tests so no real S3 call is made.
FAKE_SIGNED_URL = (
    "https://s3.amazonaws.com/jamm-test/docs/test.pdf"
    "?X-Amz-Algorithm=AWS4-HMAC-SHA256"
    "&X-Amz-Expires=3600"
    "&X-Amz-Signature=abc123"
)


def _create_portal_client(firm_id: str) -> dict:
    email = f"dl-client-{uuid.uuid4().hex[:8]}@example.com"
    password = "testpass1!"
    db = TestingSessionLocal()
    try:
        c = Client(
            firm_id=uuid.UUID(firm_id),
            name="Download Test Client",
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


def _insert_document(firm_id: str, client_id: str) -> str:
    db = TestingSessionLocal()
    try:
        doc = Document(
            firm_id=uuid.UUID(firm_id),
            client_id=uuid.UUID(client_id),
            uploaded_by=None,
            filename="quarterly_report.pdf",
            s3_key=f"docs/{uuid.uuid4()}/quarterly_report.pdf",
            content_type="application/pdf",
            size_bytes=2048,
            visibility="client_visible",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return str(doc.id)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 1: Authenticated client retrieves a signed URL for their own document
# ---------------------------------------------------------------------------

def test_client_retrieves_signed_url_for_own_document(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]

    portal_info = _create_portal_client(firm_id)
    portal_headers = _portal_login(client, firm_id, portal_info["email"], portal_info["password"])
    doc_id = _insert_document(firm_id, portal_info["client_id"])

    with patch("app.services.s3.generate_presigned_url", return_value=FAKE_SIGNED_URL):
        r = client.get(f"/portal/documents/{doc_id}/download", headers=portal_headers)

    assert r.status_code == 200, r.json()
    data = r.json()
    assert data["document_id"] == doc_id
    assert data["filename"] == "quarterly_report.pdf"
    assert data["url"] == FAKE_SIGNED_URL
    assert data["expires_in_seconds"] == PRESIGNED_URL_EXPIRY


# ---------------------------------------------------------------------------
# Test 2: Client cannot retrieve a signed URL for another client's document (404)
# ---------------------------------------------------------------------------

def test_client_cannot_download_other_clients_document(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]

    portal_a = _create_portal_client(firm_id)
    portal_b = _create_portal_client(firm_id)
    portal_b_headers = _portal_login(client, firm_id, portal_b["email"], portal_b["password"])

    # Document belongs to client A
    doc_id = _insert_document(firm_id, portal_a["client_id"])

    with patch("app.services.s3.generate_presigned_url", return_value=FAKE_SIGNED_URL):
        r = client.get(f"/portal/documents/{doc_id}/download", headers=portal_b_headers)

    assert r.status_code == 404, r.json()


# ---------------------------------------------------------------------------
# Test 3: expires_in_seconds matches the real PRESIGNED_URL_EXPIRY constant (3600)
# ---------------------------------------------------------------------------

def test_download_response_expires_in_one_hour(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]

    portal_info = _create_portal_client(firm_id)
    portal_headers = _portal_login(client, firm_id, portal_info["email"], portal_info["password"])
    doc_id = _insert_document(firm_id, portal_info["client_id"])

    with patch("app.services.s3.generate_presigned_url", return_value=FAKE_SIGNED_URL):
        r = client.get(f"/portal/documents/{doc_id}/download", headers=portal_headers)

    assert r.status_code == 200, r.json()
    assert r.json()["expires_in_seconds"] == 3600
    # PRESIGNED_URL_EXPIRY is the codebase-wide constant. Confirm it stays at 3600
    # and is not an indefinite or longer expiry.
    assert PRESIGNED_URL_EXPIRY == 3600
