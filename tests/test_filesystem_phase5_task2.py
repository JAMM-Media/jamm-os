# tests/test_filesystem_phase5_task2.py
"""
Guard tests for Filesystem Phase 5 Task 2: push to portal / unshare.

Spec reference: Filesystem Build Specification, Section 10.

Tests:
  1. Sharing a document sets visibility to 'client_visible'
  2. Unsharing sets visibility back to 'internal'
  3. Non-trio member gets 404 on both share and unshare (watched-fail)
  4. Sharing an already-shared document succeeds; updated_at unchanged
  5. Unsharing an already-internal document succeeds; updated_at unchanged
  6. Sharing a firm_library-scoped document returns 422
  7. After sharing, GET /portal/documents returns the document; before sharing it does not
  8. Share and unshare both write real DocumentAuditLog entries
"""

import io
import uuid
from datetime import timezone
from unittest.mock import patch

from app.models.client import Client
from app.models.document import Document
from app.models.document import DocumentAuditLog
from app.models.engagement import Engagement
from app.models.engagement_member import EngagementMember
from app.models.firm import Firm
from app.core.enums import UserRole
from app.core.security import get_password_hash
from app.services.portal_auth import hash_portal_password
from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_user(firm_id, role=UserRole.staff):
    email = f"user-{uuid.uuid4()}@test.com"
    password = "testpass123"
    db = TestingSessionLocal()
    try:
        from app.models.user import User
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


def _setup_client_and_engagement(test_client, headers, *, client_name=None):
    cl = test_client.post(
        "/clients/", json={"name": client_name or f"Client-{uuid.uuid4()}"}, headers=headers
    )
    assert cl.status_code == 201, cl.text
    client_id = cl.json()["id"]
    eng = test_client.post(
        "/engagements/",
        json={"name": f"Eng-{uuid.uuid4()}", "client_id": client_id},
        headers=headers,
    )
    assert eng.status_code == 201, eng.text
    return client_id, eng.json()["id"]


def _upload_staff(test_client, headers, client_id, engagement_id, filename="doc.txt"):
    with patch("app.api.documents.s3_service.upload_fileobj"):
        r = test_client.post(
            f"/documents/upload?client_id={client_id}&engagement_id={engagement_id}",
            files={"file": (filename, io.BytesIO(b"content"), "text/plain")},
            headers=headers,
        )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _get_doc_from_db(doc_id):
    db = TestingSessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc is None:
            return None
        return {
            "id": str(doc.id),
            "visibility": doc.visibility,
            "updated_at": doc.updated_at,
        }
    finally:
        db.close()


def _count_audit_log_entries(doc_id, action):
    db = TestingSessionLocal()
    try:
        return db.query(DocumentAuditLog).filter(
            DocumentAuditLog.document_id == doc_id,
            DocumentAuditLog.action == action,
        ).count()
    finally:
        db.close()


def _create_portal_client(firm_id):
    email = f"portal-{uuid.uuid4().hex[:8]}@example.com"
    password = "portalpass1!"
    db = TestingSessionLocal()
    try:
        c = Client(
            firm_id=uuid.UUID(firm_id),
            name=f"Portal Client {uuid.uuid4().hex[:6]}",
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


def _portal_login(http_client, firm_id, email, password):
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


def _insert_firm_library_doc(firm_id):
    doc_id = uuid.uuid4()
    db = TestingSessionLocal()
    try:
        doc = Document(
            id=doc_id,
            firm_id=uuid.UUID(firm_id),
            scope="firm_library",
            filename="firm-template.pdf",
            s3_key=f"{firm_id}/lib/{doc_id}/firm-template.pdf",
            content_type="application/pdf",
            size_bytes=512,
            source="staff",
        )
        db.add(doc)
        db.commit()
    finally:
        db.close()
    return str(doc_id)


# ---------------------------------------------------------------------------
# 1. Sharing a document sets visibility to 'client_visible'
# ---------------------------------------------------------------------------

class TestShareSetsVisibility:

    def test_share_sets_client_visible(self, client, firm_a_owner):
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)
        doc_id = _upload_staff(client, headers, client_id, eng_id)

        r = client.post(f"/documents/{doc_id}/share-to-portal", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["triage_status"] == "filed"

        row = _get_doc_from_db(doc_id)
        assert row["visibility"] == "client_visible", (
            f"share-to-portal must set visibility='client_visible'; got '{row['visibility']}'"
        )


# ---------------------------------------------------------------------------
# 2. Unsharing sets visibility back to 'internal'
# ---------------------------------------------------------------------------

class TestUnshareSetsInternal:

    def test_unshare_sets_internal(self, client, firm_a_owner):
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)
        doc_id = _upload_staff(client, headers, client_id, eng_id)

        # Share first.
        r = client.post(f"/documents/{doc_id}/share-to-portal", headers=headers)
        assert r.status_code == 200, r.text

        # Then unshare.
        r2 = client.post(f"/documents/{doc_id}/unshare-from-portal", headers=headers)
        assert r2.status_code == 200, r2.text

        row = _get_doc_from_db(doc_id)
        assert row["visibility"] == "internal", (
            f"unshare-from-portal must set visibility='internal'; got '{row['visibility']}'"
        )


# ---------------------------------------------------------------------------
# 3. Non-trio member gets 404 on share and unshare (watched-fail)
# ---------------------------------------------------------------------------

class TestTrioEnforcementOnShare:

    def test_non_trio_member_gets_404_on_share(self, client, firm_a_owner):
        """Plain engagement member (not administrator/manager/owner) gets 404 on share.

        Watched-fail: breaking the guard makes this test go red with the right
        reason (200 instead of 404), then restoring it goes green.
        """
        firm_id = firm_a_owner["firm_id"]
        owner_headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, owner_headers)
        doc_id = _upload_staff(client, owner_headers, client_id, eng_id)

        email, password, user_id = _create_user(firm_id, role=UserRole.staff)
        _add_member(firm_id, eng_id, user_id, is_administrator=False)
        staff_headers = _login(client, email, password)

        r = client.post(f"/documents/{doc_id}/share-to-portal", headers=staff_headers)
        assert r.status_code == 404, (
            f"Non-trio member must get 404 on share; got {r.status_code}: {r.text}"
        )

    def test_non_trio_member_gets_404_on_unshare(self, client, firm_a_owner):
        firm_id = firm_a_owner["firm_id"]
        owner_headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, owner_headers)
        doc_id = _upload_staff(client, owner_headers, client_id, eng_id)

        # Share as owner so there's something to unshare.
        client.post(f"/documents/{doc_id}/share-to-portal", headers=owner_headers)

        email, password, user_id = _create_user(firm_id, role=UserRole.staff)
        _add_member(firm_id, eng_id, user_id, is_administrator=False)
        staff_headers = _login(client, email, password)

        r = client.post(f"/documents/{doc_id}/unshare-from-portal", headers=staff_headers)
        assert r.status_code == 404, (
            f"Non-trio member must get 404 on unshare; got {r.status_code}: {r.text}"
        )

    def test_engagement_administrator_can_share(self, client, firm_a_owner):
        """Engagement administrator IS in the trio and must succeed."""
        firm_id = firm_a_owner["firm_id"]
        owner_headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, owner_headers)
        doc_id = _upload_staff(client, owner_headers, client_id, eng_id)

        email, password, user_id = _create_user(firm_id, role=UserRole.staff)
        _add_member(firm_id, eng_id, user_id, is_administrator=True)
        admin_headers = _login(client, email, password)

        r = client.post(f"/documents/{doc_id}/share-to-portal", headers=admin_headers)
        assert r.status_code == 200, (
            f"Engagement administrator must succeed on share; got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# 4. Sharing already-shared document succeeds; updated_at unchanged
# ---------------------------------------------------------------------------

class TestIdempotentShare:

    def test_share_already_shared_succeeds_no_updated_at_change(self, client, firm_a_owner):
        """Sharing an already-shared document returns 200 and does not update updated_at.

        Confirms commit-only-on-change: the DB row is not written again if the
        visibility value is already correct.
        """
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)
        doc_id = _upload_staff(client, headers, client_id, eng_id)

        # First share -- writes the row.
        r1 = client.post(f"/documents/{doc_id}/share-to-portal", headers=headers)
        assert r1.status_code == 200, r1.text

        row_after_first = _get_doc_from_db(doc_id)
        updated_at_after_first = row_after_first["updated_at"]

        # Second share -- must succeed and must NOT change updated_at.
        r2 = client.post(f"/documents/{doc_id}/share-to-portal", headers=headers)
        assert r2.status_code == 200, (
            f"Re-sharing must succeed idempotently; got {r2.status_code}: {r2.text}"
        )

        row_after_second = _get_doc_from_db(doc_id)
        assert row_after_second["updated_at"] == updated_at_after_first, (
            "Sharing an already-shared document must not change updated_at "
            f"(commit-only-on-change); was {updated_at_after_first}, got {row_after_second['updated_at']}"
        )
        assert row_after_second["visibility"] == "client_visible"


# ---------------------------------------------------------------------------
# 5. Unsharing already-internal document succeeds; updated_at unchanged
# ---------------------------------------------------------------------------

class TestIdempotentUnshare:

    def test_unshare_already_internal_succeeds_no_updated_at_change(self, client, firm_a_owner):
        """Unsharing a document that is already internal returns 200 and does not update updated_at."""
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)
        doc_id = _upload_staff(client, headers, client_id, eng_id)

        # Doc starts as 'internal' (default). Record updated_at before anything.
        row_initial = _get_doc_from_db(doc_id)
        updated_at_initial = row_initial["updated_at"]
        assert row_initial["visibility"] == "internal"

        r = client.post(f"/documents/{doc_id}/unshare-from-portal", headers=headers)
        assert r.status_code == 200, (
            f"Unsharing an already-internal document must succeed; got {r.status_code}: {r.text}"
        )

        row_after = _get_doc_from_db(doc_id)
        assert row_after["updated_at"] == updated_at_initial, (
            "Unsharing an already-internal document must not change updated_at; "
            f"was {updated_at_initial}, got {row_after['updated_at']}"
        )
        assert row_after["visibility"] == "internal"


# ---------------------------------------------------------------------------
# 6. Sharing a firm_library-scoped document returns 422
# ---------------------------------------------------------------------------

class TestFirmLibraryGuard:

    def test_share_firm_library_doc_returns_422(self, client, firm_a_owner):
        """Sharing a firm_library-scoped document returns 422.

        firm_library documents have no client_id, so pushing them to the portal
        is meaningless (per Document model scope rules: firm_library means
        client_id IS NULL AND engagement_id IS NULL). The service-layer guard
        catches this explicitly.
        """
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]

        doc_id = _insert_firm_library_doc(firm_id)

        r = client.post(f"/documents/{doc_id}/share-to-portal", headers=headers)
        assert r.status_code == 422, (
            f"Sharing firm_library doc must return 422; got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# 7. After sharing, GET /portal/documents returns the document
# ---------------------------------------------------------------------------

class TestPortalVisibility:

    def test_portal_list_shows_doc_after_share_not_before(self, client, firm_a_owner):
        """GET /portal/documents returns shared docs and excludes internal ones.

        Before sharing: document does not appear in portal list.
        After sharing: document appears.
        """
        firm_id = firm_a_owner["firm_id"]
        owner_headers = firm_a_owner["headers"]

        # Create a portal client (with portal_access_enabled and password).
        portal_info = _create_portal_client(firm_id)
        portal_client_id = portal_info["client_id"]

        # Create an engagement for this portal client (so we can upload a doc to it).
        eng_r = client.post(
            "/engagements/",
            json={"name": f"Vis-Eng-{uuid.uuid4()}", "client_id": portal_client_id},
            headers=owner_headers,
        )
        assert eng_r.status_code == 201, eng_r.text
        eng_id = eng_r.json()["id"]

        # Upload a staff document to that client's engagement.
        doc_id = _upload_staff(client, owner_headers, portal_client_id, eng_id, filename="report.pdf")

        # Log in as the portal client.
        portal_headers = _portal_login(client, firm_id, portal_info["email"], portal_info["password"])

        # Before sharing: must not appear.
        r_before = client.get("/portal/documents", headers=portal_headers)
        assert r_before.status_code == 200, r_before.text
        ids_before = [d["id"] for d in r_before.json()]
        assert doc_id not in ids_before, (
            "Document must not appear in portal before sharing"
        )

        # Share it as staff owner.
        share_r = client.post(f"/documents/{doc_id}/share-to-portal", headers=owner_headers)
        assert share_r.status_code == 200, share_r.text

        # After sharing: must appear.
        r_after = client.get("/portal/documents", headers=portal_headers)
        assert r_after.status_code == 200, r_after.text
        ids_after = [d["id"] for d in r_after.json()]
        assert doc_id in ids_after, (
            "Document must appear in portal after sharing"
        )

    def test_portal_list_excludes_doc_after_unshare(self, client, firm_a_owner):
        """After unsharing, document disappears from portal list."""
        firm_id = firm_a_owner["firm_id"]
        owner_headers = firm_a_owner["headers"]

        portal_info = _create_portal_client(firm_id)
        portal_client_id = portal_info["client_id"]

        eng_r = client.post(
            "/engagements/",
            json={"name": f"VisUns-Eng-{uuid.uuid4()}", "client_id": portal_client_id},
            headers=owner_headers,
        )
        assert eng_r.status_code == 201
        eng_id = eng_r.json()["id"]

        doc_id = _upload_staff(client, owner_headers, portal_client_id, eng_id, filename="letter.pdf")
        portal_headers = _portal_login(client, firm_id, portal_info["email"], portal_info["password"])

        # Share then confirm visible.
        client.post(f"/documents/{doc_id}/share-to-portal", headers=owner_headers)
        r_visible = client.get("/portal/documents", headers=portal_headers)
        assert doc_id in [d["id"] for d in r_visible.json()], "doc must appear after share"

        # Unshare then confirm gone.
        client.post(f"/documents/{doc_id}/unshare-from-portal", headers=owner_headers)
        r_gone = client.get("/portal/documents", headers=portal_headers)
        assert r_gone.status_code == 200
        assert doc_id not in [d["id"] for d in r_gone.json()], (
            "Document must not appear in portal after unsharing"
        )


# ---------------------------------------------------------------------------
# 8. Share and unshare write real DocumentAuditLog entries
# ---------------------------------------------------------------------------

class TestAuditLogEntries:

    def test_share_writes_audit_log(self, client, firm_a_owner):
        """share-to-portal writes a DocumentAuditLog row with action='share_to_portal'."""
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)
        doc_id = _upload_staff(client, headers, client_id, eng_id)

        count_before = _count_audit_log_entries(uuid.UUID(doc_id), "share_to_portal")
        assert count_before == 0

        client.post(f"/documents/{doc_id}/share-to-portal", headers=headers)

        count_after = _count_audit_log_entries(uuid.UUID(doc_id), "share_to_portal")
        assert count_after == 1, (
            f"Expected 1 share_to_portal audit entry; got {count_after}"
        )

    def test_unshare_writes_audit_log(self, client, firm_a_owner):
        """unshare-from-portal writes a DocumentAuditLog row with action='unshare_from_portal'."""
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)
        doc_id = _upload_staff(client, headers, client_id, eng_id)

        count_before = _count_audit_log_entries(uuid.UUID(doc_id), "unshare_from_portal")
        assert count_before == 0

        client.post(f"/documents/{doc_id}/unshare-from-portal", headers=headers)

        count_after = _count_audit_log_entries(uuid.UUID(doc_id), "unshare_from_portal")
        assert count_after == 1, (
            f"Expected 1 unshare_from_portal audit entry; got {count_after}"
        )

    def test_repeat_share_writes_second_audit_entry(self, client, firm_a_owner):
        """Repeat share on already-shared document still writes an audit entry.

        Confirms audit is written even when no DB mutation happens
        (the idempotent path).
        """
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)
        doc_id = _upload_staff(client, headers, client_id, eng_id)

        client.post(f"/documents/{doc_id}/share-to-portal", headers=headers)
        client.post(f"/documents/{doc_id}/share-to-portal", headers=headers)

        count = _count_audit_log_entries(uuid.UUID(doc_id), "share_to_portal")
        assert count == 2, (
            f"Repeat share must write two audit entries (one per call); got {count}"
        )
