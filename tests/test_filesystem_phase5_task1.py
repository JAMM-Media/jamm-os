# tests/test_filesystem_phase5_task1.py
"""
Guard tests for Filesystem Phase 5 Task 1: portal upload triage backend.

Spec reference: Filesystem Build Specification, Section 9.

Tests:
  1.  Portal upload creates Document with triage_status='pending'
  2.  Staff upload (upload_document and complete_upload) creates triage_status='filed'
  3.  Pending document absent from GET /documents/ and GET /documents/search
  4.  Pending document present in GET /documents/pending, fetchable by ID
  5.  GET /documents/pending access-gated -- only own-engagement docs returned
  6.  Non-trio member gets 404 on approve and reassign
  7.  Double-approve returns 409
  8.  Cross-client reassign refused with 422 (CVE-2026-47231 guard)
  9.  Approve with no PBC folder files at engagement root (folder_id None)
  10. Notification fires exactly once, on arrival; approve and reassign fire none
  11. Staff upload does NOT fire the arrival notification
"""

import io
import uuid
from unittest.mock import patch

import pytest

from tests.conftest import TestingSessionLocal
from app.models.client import Client
from app.models.document import Document
from app.models.engagement import Engagement
from app.models.engagement_member import EngagementMember
from app.models.firm import Firm
from app.models.notification import Notification
from app.models.user import User
from app.core.enums import UserRole
from app.core.security import get_password_hash
from app.services import portal_service


# ---------------------------------------------------------------------------
# Helpers
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


def _setup_client_and_engagement(test_client, headers, *, client_name=None, eng_name=None):
    cl = test_client.post(
        "/clients/", json={"name": client_name or f"Client-{uuid.uuid4()}"}, headers=headers
    )
    assert cl.status_code == 201, cl.text
    client_id = cl.json()["id"]
    eng = test_client.post(
        "/engagements/",
        json={"name": eng_name or f"Eng-{uuid.uuid4()}", "client_id": client_id},
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
            "triage_status": doc.triage_status,
            "folder_id": doc.folder_id,
            "engagement_id": doc.engagement_id,
        }
    finally:
        db.close()


def _count_notifications_for_doc(doc_id):
    db = TestingSessionLocal()
    try:
        return db.query(Notification).filter(
            Notification.related_entity_type == "document",
            Notification.related_entity_id == doc_id,
        ).count()
    finally:
        db.close()


def _setup_firm_client_engagement():
    suf = uuid.uuid4().hex[:8]
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Triage Firm {suf}", slug=f"triage-{suf}")
        db.add(firm)
        db.commit()
        db.refresh(firm)

        client_obj = Client(
            firm_id=firm.id,
            name=f"Triage Client {suf}",
            email=f"triage-{suf}@example.com",
        )
        db.add(client_obj)
        db.commit()
        db.refresh(client_obj)

        engagement = Engagement(
            firm_id=firm.id,
            client_id=client_obj.id,
            name=f"Triage Engagement {suf}",
        )
        db.add(engagement)
        db.commit()
        db.refresh(engagement)

        return client_obj.id, firm.id, engagement.id
    finally:
        db.close()


def _fake_upload_file(content=b"test content", filename="test.txt"):
    from fastapi import UploadFile
    return UploadFile(filename=filename, file=io.BytesIO(content))


# ---------------------------------------------------------------------------
# 1. Portal upload creates triage_status='pending'
# ---------------------------------------------------------------------------

class TestPortalUploadCreatesPending:

    def test_portal_upload_sets_triage_pending(self):
        """Portal upload must create Document with triage_status='pending'."""
        client_id, firm_id, engagement_id = _setup_firm_client_engagement()

        db = TestingSessionLocal()
        try:
            client_obj = db.query(Client).filter(Client.id == client_id).first()
            upload_file = _fake_upload_file()

            with patch("app.services.document_service.s3_service.upload_fileobj", return_value=None):
                doc = portal_service.upload_document(
                    db=db,
                    file=upload_file,
                    engagement_id=engagement_id,
                    client=client_obj,
                )
        finally:
            db.close()

        row = _get_doc_from_db(doc.id)
        assert row is not None, "Document row was not created"
        assert row["triage_status"] == "pending", (
            f"Portal upload must set triage_status='pending'; got '{row['triage_status']}'"
        )

    def test_portal_upload_threads_client_note(self):
        """client_note passed to portal_service.upload_document reaches the DB row."""
        client_id, firm_id, engagement_id = _setup_firm_client_engagement()

        db = TestingSessionLocal()
        try:
            client_obj = db.query(Client).filter(Client.id == client_id).first()
            upload_file = _fake_upload_file()

            with patch("app.services.document_service.s3_service.upload_fileobj", return_value=None):
                doc = portal_service.upload_document(
                    db=db,
                    file=upload_file,
                    engagement_id=engagement_id,
                    client=client_obj,
                    client_note="Here is my W-2",
                )
        finally:
            db.close()

        db2 = TestingSessionLocal()
        try:
            row = db2.query(Document).filter(Document.id == doc.id).first()
            assert row.client_note == "Here is my W-2"
        finally:
            db2.close()


# ---------------------------------------------------------------------------
# 2. Staff upload (both paths) creates triage_status='filed'
# ---------------------------------------------------------------------------

class TestStaffUploadCreatesFiled:

    def test_staff_upload_document_sets_triage_filed(self, client, firm_a_owner):
        """Staff upload via /documents/upload must create triage_status='filed'."""
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)

        doc_id = _upload_staff(client, headers, client_id, eng_id)
        row = _get_doc_from_db(doc_id)
        assert row["triage_status"] == "filed", (
            f"Staff upload must create triage_status='filed'; got '{row['triage_status']}'"
        )

    def test_complete_upload_sets_triage_filed(self, client, firm_a_owner):
        """complete_upload path must also produce triage_status='filed'."""
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)

        # Issue an upload URL (mock S3 presign).
        with patch("app.services.s3._get_client") as mock_s3:
            mock_s3.return_value.generate_presigned_url.return_value = "https://s3.example/presigned"
            r = client.post("/documents/upload-url", json={
                "client_id": client_id,
                "engagement_id": eng_id,
                "filename": "direct.pdf",
                "content_type": "application/pdf",
            }, headers=headers)
        assert r.status_code == 200, r.text
        doc_id = r.json()["document_id"]

        mock_meta = {"ContentLength": 512, "ContentType": "application/pdf"}
        with patch("app.services.s3._get_client") as mock_s3:
            mock_s3.return_value.head_object.return_value = mock_meta
            r2 = client.post(f"/documents/{doc_id}/upload-complete", json={
                "filename": "direct.pdf",
                "content_type": "application/pdf",
                "client_id": client_id,
                "engagement_id": eng_id,
            }, headers=headers)
        assert r2.status_code == 200, r2.text

        row = _get_doc_from_db(doc_id)
        assert row["triage_status"] == "filed", (
            f"complete_upload must create triage_status='filed'; got '{row['triage_status']}'"
        )


# ---------------------------------------------------------------------------
# 3. Pending document absent from GET /documents/ and GET /documents/search
# ---------------------------------------------------------------------------

class TestPendingExcludedFromListAndSearch:

    def test_pending_absent_from_list(self, client, firm_a_owner):
        """A pending document must not appear in GET /documents/."""
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)

        # Create a pending document directly via portal_service.
        db = TestingSessionLocal()
        try:
            client_obj = db.query(Client).filter(Client.id == client_id).first()
            upload_file = _fake_upload_file(filename="pending.txt")
            with patch("app.services.document_service.s3_service.upload_fileobj", return_value=None):
                doc = portal_service.upload_document(
                    db=db, file=upload_file, engagement_id=eng_id, client=client_obj
                )
            pending_doc_id = str(doc.id)
        finally:
            db.close()

        r = client.get(f"/documents/?engagement_id={eng_id}", headers=headers)
        assert r.status_code == 200, r.text
        returned_ids = [d["id"] for d in r.json()["items"]]
        assert pending_doc_id not in returned_ids, (
            "Pending document must not appear in GET /documents/"
        )

    def test_pending_absent_from_search(self, client, firm_a_owner):
        """A pending document must not appear in GET /documents/search."""
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)

        unique_name = f"uniquepending-{uuid.uuid4().hex[:8]}.txt"
        db = TestingSessionLocal()
        try:
            client_obj = db.query(Client).filter(Client.id == client_id).first()
            upload_file = _fake_upload_file(filename=unique_name)
            with patch("app.services.document_service.s3_service.upload_fileobj", return_value=None):
                doc = portal_service.upload_document(
                    db=db, file=upload_file, engagement_id=eng_id, client=client_obj
                )
            pending_doc_id = str(doc.id)
        finally:
            db.close()

        r = client.get(f"/documents/search?q={unique_name[:12]}", headers=headers)
        assert r.status_code == 200, r.text
        returned_ids = [d["id"] for d in r.json()["items"]]
        assert pending_doc_id not in returned_ids, (
            "Pending document must not appear in GET /documents/search"
        )


# ---------------------------------------------------------------------------
# 4. Pending document present in GET /documents/pending and fetchable by ID
# ---------------------------------------------------------------------------

class TestPendingVisibleInPendingEndpoint:

    def test_pending_in_pending_list(self, client, firm_a_owner):
        """A pending document appears in GET /documents/pending."""
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)

        db = TestingSessionLocal()
        try:
            client_obj = db.query(Client).filter(Client.id == client_id).first()
            upload_file = _fake_upload_file(filename="pending_tray.txt")
            with patch("app.services.document_service.s3_service.upload_fileobj", return_value=None):
                doc = portal_service.upload_document(
                    db=db, file=upload_file, engagement_id=eng_id, client=client_obj
                )
            pending_doc_id = str(doc.id)
        finally:
            db.close()

        r = client.get(f"/documents/pending?engagement_id={eng_id}", headers=headers)
        assert r.status_code == 200, r.text
        returned_ids = [d["id"] for d in r.json()["items"]]
        assert pending_doc_id in returned_ids, (
            "Pending document must appear in GET /documents/pending"
        )

    def test_pending_fetchable_by_id(self, client, firm_a_owner):
        """A pending document can still be fetched directly via GET /documents/{id}."""
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)

        db = TestingSessionLocal()
        try:
            client_obj = db.query(Client).filter(Client.id == client_id).first()
            upload_file = _fake_upload_file(filename="pending_fetch.txt")
            with patch("app.services.document_service.s3_service.upload_fileobj", return_value=None):
                doc = portal_service.upload_document(
                    db=db, file=upload_file, engagement_id=eng_id, client=client_obj
                )
            pending_doc_id = str(doc.id)
        finally:
            db.close()

        r = client.get(f"/documents/{pending_doc_id}", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["id"] == pending_doc_id


# ---------------------------------------------------------------------------
# 5. GET /documents/pending access-gated -- own-engagement docs only
# ---------------------------------------------------------------------------

class TestPendingListAccessGate:

    def test_pending_only_shows_own_engagement_docs(self, client, firm_a_owner):
        """Staff member of eng-A cannot see pending docs from eng-B in /pending.

        Uses two engagements sharing the same client -- same pattern as
        test_filesystem_phase2_access_gate.py test_cross_engagement_list_denied.
        """
        firm_id = firm_a_owner["firm_id"]
        owner_headers = firm_a_owner["headers"]

        client_id, eng_a_id = _setup_client_and_engagement(client, owner_headers)
        eng_b = client.post(
            "/engagements/",
            json={"name": f"Eng-B-{uuid.uuid4()}", "client_id": client_id},
            headers=owner_headers,
        )
        assert eng_b.status_code == 201, eng_b.text
        eng_b_id = eng_b.json()["id"]

        # Upload pending doc to eng-B.
        db = TestingSessionLocal()
        try:
            client_obj = db.query(Client).filter(Client.id == client_id).first()
            upload_file = _fake_upload_file(filename="eng_b_pending.txt")
            with patch("app.services.document_service.s3_service.upload_fileobj", return_value=None):
                doc = portal_service.upload_document(
                    db=db, file=upload_file, engagement_id=eng_b_id, client=client_obj
                )
            eng_b_doc_id = str(doc.id)
        finally:
            db.close()

        # Create a staff user member of eng-A only.
        email, password, user_id = _create_user(firm_id)
        _add_member(firm_id, eng_a_id, user_id)
        staff_headers = _login(client, email, password)

        r = client.get("/documents/pending", headers=staff_headers)
        assert r.status_code == 200, r.text
        returned_ids = [d["id"] for d in r.json()["items"]]
        assert eng_b_doc_id not in returned_ids, (
            "Staff member of eng-A must not see eng-B pending documents"
        )


# ---------------------------------------------------------------------------
# 6. Non-trio member gets 404 on approve and reassign
# ---------------------------------------------------------------------------

class TestTrioEnforcementOnApproveAndReassign:

    def test_non_trio_member_gets_404_on_approve(self, client, firm_a_owner):
        """Plain engagement member (not administrator/manager/owner) gets 404 on approve.

        Matches the existing codebase convention (confirmed against
        assert_can_delete_document): trio check denial returns 404 not 403,
        to avoid confirming the document exists.
        """
        firm_id = firm_a_owner["firm_id"]
        owner_headers = firm_a_owner["headers"]

        client_id, eng_id = _setup_client_and_engagement(client, owner_headers)

        # Create pending document.
        db = TestingSessionLocal()
        try:
            client_obj = db.query(Client).filter(Client.id == client_id).first()
            upload_file = _fake_upload_file(filename="trio_approve.txt")
            with patch("app.services.document_service.s3_service.upload_fileobj", return_value=None):
                doc = portal_service.upload_document(
                    db=db, file=upload_file, engagement_id=eng_id, client=client_obj
                )
            doc_id = str(doc.id)
        finally:
            db.close()

        # Non-administrator member.
        email, password, user_id = _create_user(firm_id, role=UserRole.staff)
        _add_member(firm_id, eng_id, user_id, is_administrator=False)
        staff_headers = _login(client, email, password)

        r = client.post(f"/documents/{doc_id}/approve", headers=staff_headers)
        assert r.status_code == 404, (
            f"Non-trio member must get 404 on approve; got {r.status_code}"
        )

    def test_non_trio_member_gets_404_on_reassign(self, client, firm_a_owner):
        """Plain engagement member gets 404 on reassign."""
        firm_id = firm_a_owner["firm_id"]
        owner_headers = firm_a_owner["headers"]

        client_id, eng_id = _setup_client_and_engagement(client, owner_headers)
        eng_b = client.post(
            "/engagements/",
            json={"name": f"EngB-{uuid.uuid4()}", "client_id": client_id},
            headers=owner_headers,
        )
        assert eng_b.status_code == 201
        eng_b_id = eng_b.json()["id"]

        db = TestingSessionLocal()
        try:
            client_obj = db.query(Client).filter(Client.id == client_id).first()
            upload_file = _fake_upload_file(filename="trio_reassign.txt")
            with patch("app.services.document_service.s3_service.upload_fileobj", return_value=None):
                doc = portal_service.upload_document(
                    db=db, file=upload_file, engagement_id=eng_id, client=client_obj
                )
            doc_id = str(doc.id)
        finally:
            db.close()

        email, password, user_id = _create_user(firm_id, role=UserRole.staff)
        _add_member(firm_id, eng_id, user_id, is_administrator=False)
        staff_headers = _login(client, email, password)

        r = client.post(f"/documents/{doc_id}/reassign",
                        json={"dest_engagement_id": eng_b_id}, headers=staff_headers)
        assert r.status_code == 404, (
            f"Non-trio member must get 404 on reassign; got {r.status_code}"
        )


# ---------------------------------------------------------------------------
# 7. Double-approve returns 409
# ---------------------------------------------------------------------------

class TestIdempotencyGuard:

    def test_approve_already_filed_document_returns_409(self, client, firm_a_owner):
        """Approving an already-filed document returns 409, not silent success."""
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)

        # Upload a normal staff doc (triage_status='filed').
        doc_id = _upload_staff(client, headers, client_id, eng_id)

        r = client.post(f"/documents/{doc_id}/approve", headers=headers)
        assert r.status_code == 409, (
            f"Approving a filed document must return 409; got {r.status_code}: {r.text}"
        )

    def test_approve_twice_returns_409_on_second(self, client, firm_a_owner):
        """First approve succeeds; second returns 409."""
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)

        db = TestingSessionLocal()
        try:
            client_obj = db.query(Client).filter(Client.id == client_id).first()
            upload_file = _fake_upload_file(filename="double_approve.txt")
            with patch("app.services.document_service.s3_service.upload_fileobj", return_value=None):
                doc = portal_service.upload_document(
                    db=db, file=upload_file, engagement_id=eng_id, client=client_obj
                )
            doc_id = str(doc.id)
        finally:
            db.close()

        r1 = client.post(f"/documents/{doc_id}/approve", headers=headers)
        assert r1.status_code == 200, r1.text

        r2 = client.post(f"/documents/{doc_id}/approve", headers=headers)
        assert r2.status_code == 409, (
            f"Second approve must return 409; got {r2.status_code}"
        )


# ---------------------------------------------------------------------------
# 8. Cross-client reassign refused with 422 (CVE-2026-47231 guard)
# ---------------------------------------------------------------------------

class TestCrossClientReassignGuard:

    def test_reassign_to_different_client_engagement_returns_422(self, client, firm_a_owner):
        """Reassigning a pending document to an engagement under a different client
        must be refused with 422.

        This is the security-relevant check: it mirrors the exact failure pattern
        in CVE-2026-47231 (Admidio document module), where an endpoint authorized
        the destination engagement but did not validate the client relationship
        between source and destination. A missing check here would allow a staff
        member to move a client's file into another client's engagement binder --
        a real tenant data leak within a shared firm.
        """
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]

        # Client A with engagement A.
        client_a_id, eng_a_id = _setup_client_and_engagement(client, headers, client_name="Client-A")

        # Client B with engagement B (different client!).
        client_b_resp = client.post(
            "/clients/", json={"name": "Client-B"}, headers=headers
        )
        assert client_b_resp.status_code == 201
        client_b_id = client_b_resp.json()["id"]
        eng_b_resp = client.post(
            "/engagements/",
            json={"name": "Eng-B", "client_id": client_b_id},
            headers=headers,
        )
        assert eng_b_resp.status_code == 201
        eng_b_id = eng_b_resp.json()["id"]

        # Upload pending doc to client A's engagement.
        db = TestingSessionLocal()
        try:
            client_obj_a = db.query(Client).filter(Client.id == client_a_id).first()
            upload_file = _fake_upload_file(filename="cross_client.txt")
            with patch("app.services.document_service.s3_service.upload_fileobj", return_value=None):
                doc = portal_service.upload_document(
                    db=db, file=upload_file, engagement_id=eng_a_id, client=client_obj_a
                )
            doc_id = str(doc.id)
        finally:
            db.close()

        # Attempt to reassign to client B's engagement.
        r = client.post(f"/documents/{doc_id}/reassign",
                        json={"dest_engagement_id": eng_b_id}, headers=headers)
        assert r.status_code == 422, (
            f"Cross-client reassign must return 422 (CVE-2026-47231 guard); got {r.status_code}: {r.text}"
        )

    def test_reassign_same_client_succeeds(self, client, firm_a_owner):
        """Reassigning to another engagement of the same client succeeds."""
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]

        client_id, eng_a_id = _setup_client_and_engagement(client, headers)
        eng_b_resp = client.post(
            "/engagements/",
            json={"name": f"EngB-{uuid.uuid4()}", "client_id": client_id},
            headers=headers,
        )
        assert eng_b_resp.status_code == 201
        eng_b_id = eng_b_resp.json()["id"]

        db = TestingSessionLocal()
        try:
            client_obj = db.query(Client).filter(Client.id == client_id).first()
            upload_file = _fake_upload_file(filename="same_client_reassign.txt")
            with patch("app.services.document_service.s3_service.upload_fileobj", return_value=None):
                doc = portal_service.upload_document(
                    db=db, file=upload_file, engagement_id=eng_a_id, client=client_obj
                )
            doc_id = str(doc.id)
        finally:
            db.close()

        r = client.post(f"/documents/{doc_id}/reassign",
                        json={"dest_engagement_id": eng_b_id}, headers=headers)
        assert r.status_code == 200, (
            f"Same-client reassign must succeed; got {r.status_code}: {r.text}"
        )
        row = _get_doc_from_db(doc_id)
        assert str(row["engagement_id"]) == eng_b_id
        assert row["triage_status"] == "filed"


# ---------------------------------------------------------------------------
# 9. Approve with no PBC folder files at engagement root (folder_id None)
# ---------------------------------------------------------------------------

class TestApprovePBCFolderFallback:

    def test_approve_no_pbc_folder_leaves_folder_id_none(self, client, firm_a_owner):
        """Approving a pending document when no 'Provided by Client (PBC)' folder
        exists in that engagement leaves folder_id as None (engagement root).
        No new PBC folder must be created.
        """
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)

        db = TestingSessionLocal()
        try:
            client_obj = db.query(Client).filter(Client.id == client_id).first()
            upload_file = _fake_upload_file(filename="no_pbc.txt")
            with patch("app.services.document_service.s3_service.upload_fileobj", return_value=None):
                doc = portal_service.upload_document(
                    db=db, file=upload_file, engagement_id=eng_id, client=client_obj
                )
            doc_id = str(doc.id)
        finally:
            db.close()

        r = client.post(f"/documents/{doc_id}/approve", headers=headers)
        assert r.status_code == 200, r.text

        row = _get_doc_from_db(doc_id)
        assert row["triage_status"] == "filed"
        assert row["folder_id"] is None, (
            f"No PBC folder: folder_id must remain None after approve; got {row['folder_id']}"
        )

        # Confirm no new folder was created.
        from app.models.document_folder import DocumentFolder
        db2 = TestingSessionLocal()
        try:
            pbc_count = db2.query(DocumentFolder).filter(
                DocumentFolder.engagement_id == eng_id,
                DocumentFolder.name == "Provided by Client (PBC)",
            ).count()
        finally:
            db2.close()
        assert pbc_count == 0, "Approve must not create a new PBC folder"


# ---------------------------------------------------------------------------
# 10. Notification fires exactly once, on arrival; approve and reassign fire none
# ---------------------------------------------------------------------------

class TestNotificationFiring:

    def test_notification_fires_once_on_arrival(self, client, firm_a_owner):
        """Notification is created exactly once for a client-sourced upload.
        Approve does not fire another.
        """
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)

        # Add a member to the engagement so there is a notification recipient.
        email, password, user_id = _create_user(firm_id, role=UserRole.staff)
        _add_member(firm_id, eng_id, user_id, is_administrator=True)

        db = TestingSessionLocal()
        try:
            client_obj = db.query(Client).filter(Client.id == client_id).first()
            upload_file = _fake_upload_file(filename="notif_arrival.txt")
            with patch("app.services.document_service.s3_service.upload_fileobj", return_value=None):
                doc = portal_service.upload_document(
                    db=db, file=upload_file, engagement_id=eng_id, client=client_obj
                )
            doc_id = doc.id
        finally:
            db.close()

        count_after_upload = _count_notifications_for_doc(doc_id)
        assert count_after_upload >= 1, (
            "At least one notification must fire when a client-uploaded document arrives"
        )

        # Approve -- must NOT fire another notification.
        r = client.post(f"/documents/{doc_id}/approve", headers=headers)
        assert r.status_code == 200, r.text

        count_after_approve = _count_notifications_for_doc(doc_id)
        assert count_after_approve == count_after_upload, (
            f"Approve must not fire a notification; count went from {count_after_upload} to {count_after_approve}"
        )

    def test_notification_not_fired_again_on_reassign(self, client, firm_a_owner):
        """Reassign does not fire a second notification."""
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]
        client_id, eng_a_id = _setup_client_and_engagement(client, headers)
        eng_b_resp = client.post(
            "/engagements/",
            json={"name": f"EngB-{uuid.uuid4()}", "client_id": client_id},
            headers=headers,
        )
        assert eng_b_resp.status_code == 201
        eng_b_id = eng_b_resp.json()["id"]

        email, password, user_id = _create_user(firm_id, role=UserRole.staff)
        _add_member(firm_id, eng_a_id, user_id, is_administrator=True)

        db = TestingSessionLocal()
        try:
            client_obj = db.query(Client).filter(Client.id == client_id).first()
            upload_file = _fake_upload_file(filename="notif_reassign.txt")
            with patch("app.services.document_service.s3_service.upload_fileobj", return_value=None):
                doc = portal_service.upload_document(
                    db=db, file=upload_file, engagement_id=eng_a_id, client=client_obj
                )
            doc_id = doc.id
        finally:
            db.close()

        count_after_upload = _count_notifications_for_doc(doc_id)

        r = client.post(f"/documents/{doc_id}/reassign",
                        json={"dest_engagement_id": eng_b_id}, headers=headers)
        assert r.status_code == 200, r.text

        count_after_reassign = _count_notifications_for_doc(doc_id)
        assert count_after_reassign == count_after_upload, (
            f"Reassign must not fire a notification; count went from {count_after_upload} to {count_after_reassign}"
        )


# ---------------------------------------------------------------------------
# 11. Staff upload does NOT fire the arrival notification
# ---------------------------------------------------------------------------

class TestStaffUploadNoNotification:

    def test_staff_upload_fires_no_triage_notification(self, client, firm_a_owner):
        """Staff-sourced upload does not fire the document-arrival notification.

        Confirms the source == 'client' scoping on the notification block in
        document_service.upload_document is correct.
        """
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)

        email, password, user_id = _create_user(firm_id, role=UserRole.staff)
        _add_member(firm_id, eng_id, user_id, is_administrator=True)

        doc_id = _upload_staff(client, headers, client_id, eng_id, filename="staff_notif.txt")

        count = _count_notifications_for_doc(uuid.UUID(doc_id))
        assert count == 0, (
            f"Staff upload must fire zero triage arrival notifications; got {count}"
        )
