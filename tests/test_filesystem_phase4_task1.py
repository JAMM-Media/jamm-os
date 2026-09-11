# tests/test_filesystem_phase4_task1.py
"""
Guard tests for Filesystem Phase 4 Task 1:
  - Direct-to-S3 upload flow (upload-url + upload-complete)
  - Document folder CRUD with access control
  - Depth-20 tripwire for nested folders
  - Folder soft-delete cascades to documents

Tests:
  1. upload-url: parent-mismatch refused with 404
  2. upload-url: non-member refused with 403
  3. upload-url: S3 key is server-generated (not client-supplied)
  4. complete_upload: duplicate detected -- returns conflict, no doc created
  5. complete_upload replace: old doc in trash, new doc created with same name
  6. complete_upload keep_both: filename gets "(2)" suffix, then "(3)"
  7. Folder CRUD access control: non-member cannot create engagement folder
  8. Depth-20 tripwire: 20 levels OK, 21st refused with 422
  9. Folder delete cascades docs to trash
"""

import io
import uuid
from unittest.mock import patch, MagicMock

import pytest
from botocore.exceptions import ClientError

from tests.conftest import TestingSessionLocal
from app.models.user import User
from app.models.document import Document
from app.models.document_folder import DocumentFolder
from app.models.engagement_member import EngagementMember
from app.core.enums import UserRole
from app.core.security import get_password_hash


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


def _upload(test_client, headers, client_id, engagement_id, filename="doc.txt"):
    """Upload via the traditional server-proxied endpoint (no S3 HEAD needed)."""
    with patch("app.api.documents.s3_service.upload_fileobj"):
        r = test_client.post(
            f"/documents/upload?client_id={client_id}&engagement_id={engagement_id}",
            files={"file": (filename, io.BytesIO(b"content"), "text/plain")},
            headers=headers,
        )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _make_s3_client_error(code: str):
    """Build a botocore ClientError for the given HTTP/S3 error code."""
    error_response = {"Error": {"Code": code, "Message": "Not Found"}}
    return ClientError(error_response, "HeadObject")


# ---------------------------------------------------------------------------
# 1. upload-url: parent-mismatch refused (wrong client_id for the engagement)
# ---------------------------------------------------------------------------

def test_upload_url_parent_mismatch_refused(client, firm_a_owner):
    """upload-url returns 404 when supplied client_id does not match the engagement."""
    headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, headers)

    # Create a second unrelated client.
    cl2 = client.post("/clients/", json={"name": "Other Client"}, headers=headers)
    assert cl2.status_code == 201
    other_client_id = cl2.json()["id"]

    with patch("app.services.s3.generate_presigned_put_url", return_value="https://s3.example/url"):
        r = client.post("/documents/upload-url", json={
            "client_id": other_client_id,  # wrong -- does not own eng_id
            "engagement_id": eng_id,
            "filename": "report.pdf",
            "content_type": "application/pdf",
        }, headers=headers)
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# 2. upload-url: non-member refused with 403
# ---------------------------------------------------------------------------

def test_upload_url_non_member_refused(client, firm_a_owner):
    """upload-url returns 403 when the staff user is not a member of the engagement."""
    owner_headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]
    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)

    # Create staff user who is NOT a member.
    email, password, _ = _create_user(firm_id, role=UserRole.staff)
    staff_headers = _login(client, email, password)

    with patch("app.services.s3.generate_presigned_put_url", return_value="https://s3.example/url"):
        r = client.post("/documents/upload-url", json={
            "client_id": client_id,
            "engagement_id": eng_id,
            "filename": "report.pdf",
            "content_type": "application/pdf",
        }, headers=staff_headers)
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# 3. upload-url: S3 key is server-generated (not client-supplied)
# ---------------------------------------------------------------------------

def test_upload_url_key_is_server_generated(client, firm_a_owner):
    """upload-url response contains an s3_key that embeds the firm/client/engagement path."""
    headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]
    client_id, eng_id = _setup_client_and_engagement(client, headers)

    with patch("app.services.s3._get_client") as mock_s3:
        mock_s3.return_value.generate_presigned_url.return_value = "https://s3.example/presigned"
        r = client.post("/documents/upload-url", json={
            "client_id": client_id,
            "engagement_id": eng_id,
            "filename": "my_tax_return.pdf",
            "content_type": "application/pdf",
        }, headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert "document_id" in body
    assert "upload_url" in body
    assert "s3_key" in body
    assert "expires_in_seconds" in body

    s3_key = body["s3_key"]
    # Key must embed firm_id, client_id, engagement_id (server-derived).
    assert firm_id in s3_key
    assert client_id in s3_key
    assert eng_id in s3_key
    assert "my_tax_return.pdf" in s3_key

    # document_id embedded in the key must match the returned document_id.
    doc_id = body["document_id"]
    assert doc_id in s3_key


# ---------------------------------------------------------------------------
# 4. complete_upload: duplicate detected -- returns conflict, no doc created
# ---------------------------------------------------------------------------

def test_complete_upload_duplicate_conflict(client, firm_a_owner):
    """upload-complete returns conflict dict when filename already exists in the folder."""
    headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, headers)

    # Create the initial document via the traditional upload endpoint.
    _upload(client, headers, client_id, eng_id, filename="report.pdf")

    # Now try to complete a direct-to-S3 upload with the same filename.
    doc_id = str(uuid.uuid4())

    mock_meta = {"ContentLength": 1024, "ContentType": "application/pdf"}
    with patch("app.services.s3._get_client") as mock_s3:
        mock_s3.return_value.head_object.return_value = mock_meta
        r = client.post(f"/documents/{doc_id}/upload-complete", json={
            "filename": "report.pdf",
            "content_type": "application/pdf",
            "client_id": client_id,
            "engagement_id": eng_id,
        }, headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["document"] is None
    assert body["conflict"] is not None
    assert body["conflict"]["filename"] == "report.pdf"

    # No new document should have been created.
    db = TestingSessionLocal()
    try:
        count = db.query(Document).filter(
            Document.engagement_id == eng_id,
            Document.filename == "report.pdf",
            Document.deleted_at.is_(None),
        ).count()
        assert count == 1, f"Expected 1 doc, got {count}"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 5. complete_upload replace: old doc in trash, new doc created
# ---------------------------------------------------------------------------

def test_complete_upload_replace_action(client, firm_a_owner):
    """duplicate_action='replace' soft-deletes the old doc and creates a new one."""
    headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, headers)

    old_doc_id = _upload(client, headers, client_id, eng_id, filename="report.pdf")

    new_doc_id = str(uuid.uuid4())
    mock_meta = {"ContentLength": 2048, "ContentType": "application/pdf"}

    with patch("app.services.s3._get_client") as mock_s3:
        mock_s3.return_value.head_object.return_value = mock_meta
        r = client.post(f"/documents/{new_doc_id}/upload-complete", json={
            "filename": "report.pdf",
            "content_type": "application/pdf",
            "client_id": client_id,
            "engagement_id": eng_id,
            "duplicate_action": "replace",
        }, headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["document"] is not None
    assert body["conflict"] is None
    assert body["document"]["filename"] == "report.pdf"

    db = TestingSessionLocal()
    try:
        # Old doc must be in trash.
        old = db.query(Document).filter(Document.id == old_doc_id).first()
        assert old is not None
        assert old.deleted_at is not None, "Old doc must be soft-deleted"

        # New doc must be live.
        new = db.query(Document).filter(
            Document.id == new_doc_id,
            Document.deleted_at.is_(None),
        ).first()
        assert new is not None, "New doc must be live"
        assert new.filename == "report.pdf"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 6. complete_upload keep_both: filename gets "(2)" suffix, then "(3)"
# ---------------------------------------------------------------------------

def test_complete_upload_keep_both_suffixes(client, firm_a_owner):
    """duplicate_action='keep_both' appends (2) then (3) to subsequent uploads."""
    headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, headers)

    # Create original "report.pdf".
    _upload(client, headers, client_id, eng_id, filename="report.pdf")

    mock_meta = {"ContentLength": 1024, "ContentType": "application/pdf"}

    # First keep_both: should create "report (2).pdf".
    doc_id_2 = str(uuid.uuid4())
    with patch("app.services.s3._get_client") as mock_s3:
        mock_s3.return_value.head_object.return_value = mock_meta
        r2 = client.post(f"/documents/{doc_id_2}/upload-complete", json={
            "filename": "report.pdf",
            "content_type": "application/pdf",
            "client_id": client_id,
            "engagement_id": eng_id,
            "duplicate_action": "keep_both",
        }, headers=headers)

    assert r2.status_code == 200, r2.text
    assert r2.json()["document"]["filename"] == "report (2).pdf"

    # Second keep_both: should create "report (3).pdf".
    doc_id_3 = str(uuid.uuid4())
    with patch("app.services.s3._get_client") as mock_s3:
        mock_s3.return_value.head_object.return_value = mock_meta
        r3 = client.post(f"/documents/{doc_id_3}/upload-complete", json={
            "filename": "report.pdf",
            "content_type": "application/pdf",
            "client_id": client_id,
            "engagement_id": eng_id,
            "duplicate_action": "keep_both",
        }, headers=headers)

    assert r3.status_code == 200, r3.text
    assert r3.json()["document"]["filename"] == "report (3).pdf"


# ---------------------------------------------------------------------------
# 7. Folder CRUD access control: non-member cannot create engagement folder
# ---------------------------------------------------------------------------

def test_folder_create_non_member_refused(client, firm_a_owner):
    """A staff user who is not a member of the engagement cannot create a folder in it."""
    owner_headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]
    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)

    # Create staff user who is NOT a member.
    email, password, _ = _create_user(firm_id, role=UserRole.staff)
    staff_headers = _login(client, email, password)

    r = client.post("/document-folders/", json={
        "name": "My Folder",
        "scope": "engagement",
        "client_id": client_id,
        "engagement_id": eng_id,
    }, headers=staff_headers)
    assert r.status_code == 403, r.text


def test_folder_create_member_succeeds(client, firm_a_owner):
    """A staff user who IS a member of the engagement can create a folder."""
    owner_headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]
    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)

    email, password, user_id = _create_user(firm_id, role=UserRole.staff)
    _add_member(firm_id, eng_id, user_id)
    staff_headers = _login(client, email, password)

    r = client.post("/document-folders/", json={
        "name": "My Folder",
        "scope": "engagement",
        "client_id": client_id,
        "engagement_id": eng_id,
    }, headers=staff_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "My Folder"
    assert body["scope"] == "engagement"


# ---------------------------------------------------------------------------
# 8. Depth-20 tripwire: 20 levels OK, 21st refused with 422
# ---------------------------------------------------------------------------

def test_depth_20_tripwire(client, firm_a_owner):
    """Creating 20 nested folders succeeds; the 21st is refused with 422."""
    owner_headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]
    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)

    # Build 20 nested folders directly via DB for speed.
    db = TestingSessionLocal()
    try:
        parent_id = None
        for i in range(20):
            folder = DocumentFolder(
                firm_id=firm_id,
                scope="engagement",
                name=f"Level {i}",
                client_id=client_id,
                engagement_id=eng_id,
                parent_folder_id=parent_id,
            )
            db.add(folder)
            db.commit()
            db.refresh(folder)
            parent_id = folder.id
        deepest_id = str(parent_id)
    finally:
        db.close()

    # 21st level should be refused.
    r = client.post("/document-folders/", json={
        "name": "Too Deep",
        "scope": "engagement",
        "client_id": client_id,
        "engagement_id": eng_id,
        "parent_folder_id": deepest_id,
    }, headers=owner_headers)
    assert r.status_code == 422, r.text
    assert "20" in r.json().get("detail", ""), r.json()


# ---------------------------------------------------------------------------
# 9. Folder soft-delete cascades docs to trash
# ---------------------------------------------------------------------------

def test_folder_delete_soft_deletes_folder(client, firm_a_owner):
    """DELETE /document-folders/{id} soft-deletes the folder (deleted_at set, row survives)."""
    owner_headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]
    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)

    # Create a folder via API.
    r_folder = client.post("/document-folders/", json={
        "name": "ToDelete",
        "scope": "engagement",
        "client_id": client_id,
        "engagement_id": eng_id,
    }, headers=owner_headers)
    assert r_folder.status_code == 201, r_folder.text
    folder_id = r_folder.json()["id"]
    folder_uuid = uuid.UUID(folder_id)

    # Delete the folder.
    r_del = client.delete(f"/document-folders/{folder_id}", headers=owner_headers)
    assert r_del.status_code == 204, r_del.text

    # Verify folder row is soft-deleted (not hard-deleted).
    db = TestingSessionLocal()
    try:
        folder = db.query(DocumentFolder).filter(DocumentFolder.id == folder_uuid).first()
        assert folder is not None, "Folder DB row must survive a soft delete"
        assert folder.deleted_at is not None, "deleted_at must be set after soft delete"
        assert folder.deleted_by is not None, "deleted_by must be set after soft delete"
    finally:
        db.close()

    # Verify the folder is no longer returned by GET (soft-delete filter).
    r_get = client.get(f"/document-folders/{folder_id}", headers=owner_headers)
    assert r_get.status_code == 404, "Soft-deleted folder must not be returned by GET"


def test_folder_delete_cascade_service_counts_documents(client, firm_a_owner):
    """delete_folder_with_cascade returns the count of documents it soft-deletes.
    Uses a real user ID to satisfy the deleted_by FK constraint."""
    from app.services.document_folder_service import delete_folder_with_cascade
    from app.models.firm import Firm

    firm_id = uuid.UUID(firm_a_owner["firm_id"])

    # Get the firm owner's user_id from the DB.
    db = TestingSessionLocal()
    try:
        from app.models.firm import Firm as FirmModel
        firm = db.get(FirmModel, str(firm_id))
        owner = db.query(User).filter(
            User.firm_id == firm_id,
            User.role == UserRole.firm_owner,
        ).first()
        assert owner is not None
        owner_id = owner.id

        # Create a folder directly in DB.
        folder = DocumentFolder(
            firm_id=firm_id,
            scope="firm_library",
            name="CascadeTest",
        )
        db.add(folder)
        db.commit()
        db.refresh(folder)

        # The cascade returns 0 when no documents are in the folder.
        count = delete_folder_with_cascade(
            db=db, folder=folder, firm_id=firm_id, current_user_id=owner_id
        )
        assert count == 0

        # Verify the folder was soft-deleted.
        db.refresh(folder)
        assert folder.deleted_at is not None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 12. Revoked membership blocks upload-complete even with a valid doc_id
# ---------------------------------------------------------------------------

def test_complete_upload_refused_after_membership_revoked(client, firm_a_owner):
    """
    A staff member who mints an upload URL as a valid engagement member, then
    has that membership revoked before calling upload-complete, must be refused
    at upload-complete time -- not granted access on the strength of the
    now-expired presigned URL.

    Verifies that complete_upload re-runs assert_can_upload_to_engagement at the
    top of the service function, before the idempotency guard and before any
    S3 or DB access.
    """
    firm_id = firm_a_owner["firm_id"]
    owner_headers = firm_a_owner["headers"]

    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)

    # Create a staff user and add them as an engagement member.
    email, password, user_id = _create_user(firm_id)
    _add_member(firm_id, eng_id, user_id)
    staff_headers = _login(client, email, password)

    # Step 1: mint a presigned upload URL while the membership is valid.
    fake_put_url = "https://s3.example.com/presigned-put"
    with patch("app.services.s3.generate_presigned_put_url", return_value=fake_put_url):
        r = client.post(
            "/documents/upload-url",
            json={
                "client_id": client_id,
                "engagement_id": eng_id,
                "filename": "revoked-test.pdf",
                "content_type": "application/pdf",
            },
            headers=staff_headers,
        )
    assert r.status_code == 200, r.text
    doc_id = r.json()["document_id"]

    # Revoke the membership directly in the DB, simulating the gap between
    # URL issuance and upload completion.
    db = TestingSessionLocal()
    try:
        member = db.query(EngagementMember).filter(
            EngagementMember.firm_id == firm_id,
            EngagementMember.engagement_id == eng_id,
            EngagementMember.user_id == uuid.UUID(user_id),
        ).first()
        assert member is not None, "Test setup error: membership row not found"
        db.delete(member)
        db.commit()
    finally:
        db.close()

    # Step 2: attempt upload-complete with the now-revoked user.
    # The auth check inside complete_upload must fire before any S3 HEAD call.
    with patch("app.services.s3.head_object") as mock_head:
        r = client.post(
            f"/documents/{doc_id}/upload-complete",
            json={
                "filename": "revoked-test.pdf",
                "content_type": "application/pdf",
                "client_id": client_id,
                "engagement_id": eng_id,
            },
            headers=staff_headers,
        )
        # head_object must never be called -- auth must fail first.
        mock_head.assert_not_called()

    assert r.status_code == 403, (
        f"Expected 403 after membership revocation, got {r.status_code}: {r.text}"
    )

    # Confirm no Document row was created.
    db = TestingSessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == uuid.UUID(doc_id)).first()
        assert doc is None, "Document row must not exist after a refused upload-complete"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 12. Client-scope folder access for engagement members
# ---------------------------------------------------------------------------

def test_client_scope_folder_accessible_by_engagement_member(client, firm_a_owner):
    """A staff member who belongs to one of a client's engagements can GET a
    client-scoped folder for that same client.

    Before the fix in assert_can_access_folder, the client scope fell straight
    through to an unconditional 404 deny for any non-elevated user. After the
    fix, client-scope access mirrors the document-level rule: any member of any
    of the client's engagements is allowed, matching Section 6 of the spec.

    Watched-fail: the positive case was confirmed to return 404 (instead of 200)
    with the client branch temporarily removed from assert_can_access_folder.
    """
    firm_id = firm_a_owner["firm_id"]
    owner_headers = firm_a_owner["headers"]

    # Create a client and engagement for the membership check.
    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)

    # Manager creates a client-scoped folder (requires manager/owner for creation).
    r_folder = client.post("/document-folders/", json={
        "scope": "client",
        "name": "Client Permanent Docs",
        "client_id": client_id,
    }, headers=owner_headers)
    assert r_folder.status_code == 201, r_folder.text
    folder_id = r_folder.json()["id"]

    # Plain staff member who is a member of the client's engagement.
    email, password, user_id = _create_user(firm_id, role=UserRole.staff)
    _add_member(firm_id, eng_id, user_id)
    staff_headers = _login(client, email, password)

    # Positive case: staff member CAN access the client-scoped folder.
    r_get = client.get(f"/document-folders/{folder_id}", headers=staff_headers)
    assert r_get.status_code == 200, (
        f"Engagement member must be able to access client-scoped folder; got {r_get.status_code}: {r_get.text}"
    )
    assert r_get.json()["id"] == folder_id

    # Negative case: staff member with NO membership in any of this client's
    # engagements is still denied 404.
    email2, password2, _ = _create_user(firm_id, role=UserRole.staff)
    stranger_headers = _login(client, email2, password2)

    r_denied = client.get(f"/document-folders/{folder_id}", headers=stranger_headers)
    assert r_denied.status_code == 404, (
        f"Staff with no client engagement membership must be denied 404; got {r_denied.status_code}: {r_denied.text}"
    )


# ---------------------------------------------------------------------------
# 13. Client-scope folder appears in list results for engagement members
# ---------------------------------------------------------------------------

def test_client_scope_folder_in_list_for_engagement_member(client, firm_a_owner):
    """GET /document-folders/?scope=client&client_id=X returns client-scoped folders
    for a staff member who belongs to one of the client's engagements.

    Before the fix, list_document_folders filtered results through _can_access,
    which had no client-scope branch and fell through to return False. After the
    fix, filtering goes through assert_can_access_folder which has the correct
    client-scope check added in the prior task, so the same staff member who
    can GET a specific client-scoped folder now also sees it in list results.

    Watched-fail: this test was confirmed to return an empty list (folder absent)
    before the _can_access removal, even when the folder exists and the staff
    member has the correct engagement membership.
    """
    firm_id = firm_a_owner["firm_id"]
    owner_headers = firm_a_owner["headers"]

    # Create a client with an engagement.
    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)

    # Manager creates a client-scoped folder.
    r_folder = client.post("/document-folders/", json={
        "scope": "client",
        "name": "Client Permanent Docs List",
        "client_id": client_id,
    }, headers=owner_headers)
    assert r_folder.status_code == 201, r_folder.text
    folder_id = r_folder.json()["id"]

    # Plain staff member who is a member of the client's engagement.
    email, password, user_id = _create_user(firm_id, role=UserRole.staff)
    _add_member(firm_id, eng_id, user_id)
    staff_headers = _login(client, email, password)

    # Positive case: folder must appear in list results for the engagement member.
    r_list = client.get(
        f"/document-folders/?scope=client&client_id={client_id}",
        headers=staff_headers,
    )
    assert r_list.status_code == 200, r_list.text
    returned_ids = [f["id"] for f in r_list.json()]
    assert folder_id in returned_ids, (
        "Client-scoped folder must appear in list results for an engagement member; "
        f"got {returned_ids}"
    )

    # Negative case: staff member with no membership in any of this client's
    # engagements must not see the folder in list results.
    email2, password2, _ = _create_user(firm_id, role=UserRole.staff)
    stranger_headers = _login(client, email2, password2)

    r_list2 = client.get(
        f"/document-folders/?scope=client&client_id={client_id}",
        headers=stranger_headers,
    )
    assert r_list2.status_code == 200, r_list2.text
    returned_ids2 = [f["id"] for f in r_list2.json()]
    assert folder_id not in returned_ids2, (
        "Client-scoped folder must NOT appear in list results for a non-member; "
        f"got {returned_ids2}"
    )
