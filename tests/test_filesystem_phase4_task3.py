# tests/test_filesystem_phase4_task3.py
"""
Guard tests for Filesystem Phase 4 Task 3: preview and keyword search.

Tests:
  1. test_preview_pdf_returns_url
  2. test_preview_unsupported_type_returns_not_available
  3. test_preview_spoofed_content_type_rejected
  4. test_preview_access_denied_returns_404
  5. test_search_finds_by_substring
  6. test_search_scoped_by_access
  7. test_search_literal_percent_in_filename
  8. test_search_total_reflects_authorized_set
  9. test_search_minimum_length_enforced
"""

import io
import uuid
from unittest.mock import patch

import pytest

from tests.conftest import TestingSessionLocal
from app.models.user import User
from app.models.document import Document
from app.models.engagement_member import EngagementMember
from app.core.enums import UserRole
from app.core.security import get_password_hash


# ---------------------------------------------------------------------------
# Helpers (mirror pattern from Phase 4 Task 1 and Task 2)
# ---------------------------------------------------------------------------

def _create_user(firm_id, role=UserRole.staff):
    email = f"user-{uuid.uuid4()}@test.com"
    password = "testpass123"
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=email,
            hashed_password=get_password_hash(password),
            full_name="Test User",
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = str(user.id)
    finally:
        db.close()
    return email, password, user_id


def _add_member(firm_id, engagement_id, user_id, *, is_administrator=False):
    db = TestingSessionLocal()
    try:
        member = EngagementMember(
            firm_id=firm_id,
            engagement_id=engagement_id,
            user_id=user_id,
            is_administrator=is_administrator,
        )
        db.add(member)
        db.commit()
    finally:
        db.close()


def _login(test_client, email, password):
    r = test_client.post("/auth/token", json={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup_client_and_engagement(test_client, headers):
    cl = test_client.post(
        "/clients/", json={"name": f"Client-{uuid.uuid4()}"}, headers=headers
    )
    assert cl.status_code == 201
    client_id = cl.json()["id"]
    eng = test_client.post(
        "/engagements/",
        json={"name": f"Eng-{uuid.uuid4()}", "client_id": client_id},
        headers=headers,
    )
    assert eng.status_code == 201
    return client_id, eng.json()["id"]


def _upload(test_client, headers, client_id, engagement_id, filename="doc.pdf",
            content_type="text/plain"):
    """Upload via the server-proxied endpoint with s3_service.upload_fileobj mocked."""
    with patch("app.api.documents.s3_service.upload_fileobj"):
        r = test_client.post(
            f"/documents/upload?client_id={client_id}&engagement_id={engagement_id}",
            files={"file": (filename, io.BytesIO(b"content"), content_type)},
            headers=headers,
        )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# 1. test_preview_pdf_returns_url
# ---------------------------------------------------------------------------

def test_preview_pdf_returns_url(client, firm_a_owner):
    """Upload a PDF doc, mock magic bytes to return PDF header, expect preview_available=True."""
    owner_headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)

    doc_id = _upload(client, owner_headers, client_id, eng_id,
                     filename="report.pdf", content_type="application/pdf")

    with patch("app.services.s3.get_object_bytes_range", return_value=b"%PDF-1.4"):
        with patch("app.api.documents.s3_service.generate_presigned_url",
                   return_value="https://s3.example.com/presigned"):
            r = client.get(f"/documents/{doc_id}/preview", headers=owner_headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["preview_available"] is True
    assert body["url"] is not None
    assert "expires_in_seconds" in body


# ---------------------------------------------------------------------------
# 2. test_preview_unsupported_type_returns_not_available
# ---------------------------------------------------------------------------

def test_preview_unsupported_type_returns_not_available(client, firm_a_owner):
    """A docx file (unsupported MIME type) returns preview_available=False with no url."""
    owner_headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)

    docx_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    doc_id = _upload(client, owner_headers, client_id, eng_id,
                     filename="contract.docx", content_type=docx_mime)

    # No S3 mock needed: content_type check fails before any S3 call.
    r = client.get(f"/documents/{doc_id}/preview", headers=owner_headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["preview_available"] is False
    assert body.get("url") is None


# ---------------------------------------------------------------------------
# 3. test_preview_spoofed_content_type_rejected
# ---------------------------------------------------------------------------

def test_preview_spoofed_content_type_rejected(client, firm_a_owner):
    """A file stored as application/pdf but with ZIP magic bytes is rejected."""
    owner_headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)

    doc_id = _upload(client, owner_headers, client_id, eng_id,
                     filename="disguised.pdf", content_type="application/pdf")

    # ZIP/docx magic bytes -- not a PDF.
    with patch("app.services.s3.get_object_bytes_range",
               return_value=b"PK\x03\x04..."):
        r = client.get(f"/documents/{doc_id}/preview", headers=owner_headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["preview_available"] is False
    assert body.get("url") is None


# ---------------------------------------------------------------------------
# 4. test_preview_access_denied_returns_404
# ---------------------------------------------------------------------------

def test_preview_access_denied_returns_404(client, firm_a_owner, firm_b_owner):
    """Cross-tenant preview attempt returns 404 (same as access denied for a live doc)."""
    owner_a_headers = firm_a_owner["headers"]
    owner_b_headers = firm_b_owner["headers"]

    client_id, eng_id = _setup_client_and_engagement(client, owner_a_headers)
    doc_id = _upload(client, owner_a_headers, client_id, eng_id,
                     filename="firm_a_doc.pdf", content_type="application/pdf")

    # Firm B owner tries to preview Firm A's document.
    r = client.get(f"/documents/{doc_id}/preview", headers=owner_b_headers)
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# 5. test_search_finds_by_substring
# ---------------------------------------------------------------------------

def test_search_finds_by_substring(client, firm_a_owner):
    """Searching for a substring of a filename returns the matching document."""
    owner_headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)

    doc_id = _upload(client, owner_headers, client_id, eng_id,
                     filename="quarterly-report-2026.pdf", content_type="application/pdf")

    r = client.get("/documents/search?q=quarterly", headers=owner_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    ids = [item["id"] for item in body["items"]]
    assert doc_id in ids, f"Expected {doc_id} in search results, got {ids}"


# ---------------------------------------------------------------------------
# 6. test_search_scoped_by_access
# ---------------------------------------------------------------------------

def test_search_scoped_by_access(client, firm_a_owner):
    """Staff in engagement A cannot find documents in engagement B via search."""
    owner_headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]

    client_id_a, eng_id_a = _setup_client_and_engagement(client, owner_headers)
    client_id_b, eng_id_b = _setup_client_and_engagement(client, owner_headers)

    # Upload secret.pdf into engagement B.
    _upload(client, owner_headers, client_id_b, eng_id_b,
            filename="secret.pdf", content_type="application/pdf")

    # Staff member only in engagement A.
    email, password, user_id = _create_user(firm_id, role=UserRole.staff)
    _add_member(firm_id, eng_id_a, user_id)
    staff_headers = _login(client, email, password)

    r = client.get("/documents/search?q=secret", headers=staff_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 0, f"Expected 0 results, got {body['total']}: {body['items']}"


# ---------------------------------------------------------------------------
# 7. test_search_literal_percent_in_filename
# ---------------------------------------------------------------------------

def test_search_literal_percent_in_filename(client, firm_a_owner):
    """Searching for '100%' finds the file with a literal percent in its name.
    Searching for bare '%' does NOT return all documents (wildcard is escaped).
    """
    owner_headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]
    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)

    # Upload 'alpha.pdf' via the API to confirm it would match a real wildcard.
    _upload(client, owner_headers, client_id, eng_id,
            filename="alpha.pdf", content_type="application/pdf")

    # Insert a doc with a literal percent in the filename directly via DB,
    # since the upload API may restrict characters.
    db = TestingSessionLocal()
    try:
        doc = Document(
            id=uuid.uuid4(),
            firm_id=firm_id,
            client_id=client_id,
            engagement_id=eng_id,
            scope="engagement",
            uploaded_by=None,
            source="staff",
            filename="Q3 100% complete.pdf",
            s3_key=f"test/{uuid.uuid4()}/Q3-100pct.pdf",
            content_type="application/pdf",
            size_bytes=100,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        percent_doc_id = str(doc.id)
    finally:
        db.close()

    # Search for "100%" -- must find only the percent doc.
    r = client.get("/documents/search?q=100%25", headers=owner_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    ids = [item["id"] for item in body["items"]]
    assert percent_doc_id in ids, f"Expected percent doc in results, got {ids}"

    # Search for bare "%" -- must NOT return all documents (wildcard is escaped).
    # If percent were treated as SQL wildcard, it would match everything.
    # After proper escaping, it matches only docs with literal "%" in name.
    r2 = client.get("/documents/search?q=%25%25", headers=owner_headers)
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    ids2 = [item["id"] for item in body2["items"]]
    # alpha.pdf has no percent; it must NOT appear.
    alpha_ids = [i for i in ids2 if "alpha" in i]
    for item in body2["items"]:
        assert "%" in item["filename"], (
            f"Bare percent search matched a doc without literal % in name: {item['filename']}"
        )


# ---------------------------------------------------------------------------
# 8. test_search_total_reflects_authorized_set
# ---------------------------------------------------------------------------

def test_search_total_reflects_authorized_set(client, firm_a_owner):
    """total in search response counts only authorized docs, not the raw DB match count."""
    owner_headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]

    client_id_a, eng_id_a = _setup_client_and_engagement(client, owner_headers)
    client_id_b, eng_id_b = _setup_client_and_engagement(client, owner_headers)

    # Upload two docs in eng_a, one in eng_b, all named to match "report".
    _upload(client, owner_headers, client_id_a, eng_id_a,
            filename="report-1.pdf", content_type="application/pdf")
    _upload(client, owner_headers, client_id_a, eng_id_a,
            filename="report-2.pdf", content_type="application/pdf")
    _upload(client, owner_headers, client_id_b, eng_id_b,
            filename="report-3.pdf", content_type="application/pdf")

    # Staff member only in eng_a -- can only see docs from eng_a.
    email, password, user_id = _create_user(firm_id, role=UserRole.staff)
    _add_member(firm_id, eng_id_a, user_id)
    staff_headers = _login(client, email, password)

    r = client.get("/documents/search?q=report", headers=staff_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 2, (
        f"Expected total=2 (only eng_a docs), got {body['total']}: {body['items']}"
    )


# ---------------------------------------------------------------------------
# 9. test_search_minimum_length_enforced
# ---------------------------------------------------------------------------

def test_search_minimum_length_enforced(client, firm_a_owner):
    """A single-character search query is rejected with 422 (min_length=2)."""
    owner_headers = firm_a_owner["headers"]

    r = client.get("/documents/search?q=a", headers=owner_headers)
    assert r.status_code == 422, r.text
