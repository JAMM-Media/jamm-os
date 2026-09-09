# tests/test_filesystem_phase3_soft_delete.py
"""
Guard tests for Filesystem Phase 3: soft delete, trash, restore, and purge.

Spec reference: Filesystem Build Specification, Section 8.

Tests:
  1. DELETE soft-deletes: deleted_at/deleted_by set, DB row survives, S3 not called
  2. Soft-deleted doc invisible on list, get, download, audit
  3. Trash endpoint: visible for authorized user, blocked for unauthorized
  4. Restore: clears deleted_at/deleted_by, doc reappears in normal listing, folder_id preserved
  5. Non-trio member refused on delete and restore
  6. Purge refused for manager (owner-only restriction)
  7. Purge without confirm=true refused, no DB or S3 side effects
  8. Real purge: calls delete_object, hard-deletes row (only test expecting delete_object)
  9. purge-all respects scope boundary
"""

import io
import uuid
from unittest.mock import patch, call

import pytest

from tests.conftest import TestingSessionLocal
from app.models.user import User
from app.models.document import Document
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
    with patch("app.api.documents.s3_service.upload_fileobj"):
        r = test_client.post(
            f"/documents/upload?client_id={client_id}&engagement_id={engagement_id}",
            files={"file": (filename, io.BytesIO(b"content"), "text/plain")},
            headers=headers,
        )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _soft_delete(test_client, headers, doc_id):
    r = test_client.delete(f"/documents/{doc_id}", headers=headers)
    assert r.status_code == 204, r.text


def _get_doc_from_db(doc_id):
    """Read document row directly from DB, bypassing soft-delete filters."""
    db = TestingSessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc is None:
            return None
        return {
            "id": str(doc.id),
            "deleted_at": doc.deleted_at,
            "deleted_by": doc.deleted_by,
            "folder_id": doc.folder_id,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1. DELETE soft-deletes: S3 not called, DB row survives, deleted_at set
# ---------------------------------------------------------------------------

def test_delete_is_soft_delete(client, firm_a_owner):
    """DELETE sets deleted_at/deleted_by, leaves DB row intact, never calls delete_object."""
    headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, headers)

    with patch("app.api.documents.s3_service.delete_object") as mock_del:
        doc_id = _upload(client, headers, client_id, eng_id)
        r = client.delete(f"/documents/{doc_id}", headers=headers)
        assert r.status_code == 204
        mock_del.assert_not_called()

    row = _get_doc_from_db(uuid.UUID(doc_id))
    assert row is not None, "DB row must survive a soft delete"
    assert row["deleted_at"] is not None, "deleted_at must be set after soft delete"
    assert row["deleted_by"] is not None, "deleted_by must be set after soft delete"


# ---------------------------------------------------------------------------
# 2. Soft-deleted doc invisible on all live read paths
# ---------------------------------------------------------------------------

def test_soft_deleted_doc_hidden_from_list(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, headers)
    doc_id = _upload(client, headers, client_id, eng_id)
    _soft_delete(client, headers, doc_id)

    r = client.get("/documents/", headers=headers)
    assert r.status_code == 200
    assert all(d["id"] != doc_id for d in r.json()["items"]), "Deleted doc must not appear in list"


def test_soft_deleted_doc_get_returns_404(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, headers)
    doc_id = _upload(client, headers, client_id, eng_id)
    _soft_delete(client, headers, doc_id)

    r = client.get(f"/documents/{doc_id}", headers=headers)
    assert r.status_code == 404


def test_soft_deleted_doc_download_returns_404(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, headers)
    doc_id = _upload(client, headers, client_id, eng_id)
    _soft_delete(client, headers, doc_id)

    with patch("app.api.documents.s3_service.generate_presigned_url") as mock_url:
        r = client.get(f"/documents/{doc_id}/download", headers=headers)
        mock_url.assert_not_called()
    assert r.status_code == 404


def test_soft_deleted_doc_audit_returns_404(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, headers)
    doc_id = _upload(client, headers, client_id, eng_id)
    _soft_delete(client, headers, doc_id)

    r = client.get(f"/documents/{doc_id}/audit", headers=headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 3. Trash endpoint: authorized user sees it, unauthorized does not
# ---------------------------------------------------------------------------

def test_trash_shows_soft_deleted_doc(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, headers)
    doc_id = _upload(client, headers, client_id, eng_id)
    _soft_delete(client, headers, doc_id)

    r = client.get("/documents/trash", headers=headers)
    assert r.status_code == 200
    ids = [d["id"] for d in r.json()["items"]]
    assert doc_id in ids, "Deleted doc must appear in trash"


def test_trash_not_accessible_to_unauthorized_user(client, firm_a_owner):
    """A staff user not in the engagement cannot see that engagement's trash."""
    firm_id = firm_a_owner["firm_id"]
    owner_headers = firm_a_owner["headers"]

    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)
    doc_id = _upload(client, owner_headers, client_id, eng_id)
    _soft_delete(client, owner_headers, doc_id)

    # Staff with no engagement memberships
    email, password, _ = _create_user(firm_id)
    staff_headers = _login(client, email, password)

    r = client.get("/documents/trash", headers=staff_headers)
    assert r.status_code == 200
    ids = [d["id"] for d in r.json()["items"]]
    assert doc_id not in ids, "Unauthorized user must not see engagement's trash"


def test_trash_shows_correct_deleted_at_and_by(client, firm_a_owner):
    """Trash listing includes deleted_at and deleted_by metadata."""
    headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, headers)
    doc_id = _upload(client, headers, client_id, eng_id)
    _soft_delete(client, headers, doc_id)

    r = client.get("/documents/trash", headers=headers)
    assert r.status_code == 200
    item = next((d for d in r.json()["items"] if d["id"] == doc_id), None)
    assert item is not None
    assert item["deleted_at"] is not None
    assert item["deleted_by"] is not None


# ---------------------------------------------------------------------------
# 4. Restore: clears soft-delete state, doc reappears in normal listing
# ---------------------------------------------------------------------------

def test_restore_clears_deleted_at_and_by(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, headers)
    doc_id = _upload(client, headers, client_id, eng_id)
    _soft_delete(client, headers, doc_id)

    r = client.post(f"/documents/{doc_id}/restore", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["deleted_at"] is None
    assert data["deleted_by"] is None


def test_restore_reappears_in_normal_list(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, headers)
    doc_id = _upload(client, headers, client_id, eng_id)
    _soft_delete(client, headers, doc_id)

    client.post(f"/documents/{doc_id}/restore", headers=headers)

    r = client.get("/documents/", headers=headers)
    assert r.status_code == 200
    ids = [d["id"] for d in r.json()["items"]]
    assert doc_id in ids, "Restored doc must reappear in normal list"


def test_restore_preserves_folder_id(client, firm_a_owner):
    """folder_id is preserved through soft-delete and restore (not zeroed by either).

    Uses a DocumentFolder row to satisfy the FK constraint (documents.folder_id
    now references document_folders, updated in Phase 4 Task 2).
    """
    from app.models.document_folder import DocumentFolder

    firm_id = firm_a_owner["firm_id"]
    headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, headers)
    doc_id = _upload(client, headers, client_id, eng_id)

    # Create a real DocumentFolder row so the FK constraint is satisfied.
    db = TestingSessionLocal()
    try:
        folder = DocumentFolder(
            firm_id=firm_id,
            scope="engagement",
            client_id=uuid.UUID(client_id),
            engagement_id=uuid.UUID(eng_id),
            name="Test Folder",
        )
        db.add(folder)
        db.commit()
        folder_id = folder.id

        doc = db.query(Document).filter(Document.id == uuid.UUID(doc_id)).first()
        doc.folder_id = folder_id
        db.commit()
    finally:
        db.close()

    _soft_delete(client, headers, doc_id)

    row = _get_doc_from_db(uuid.UUID(doc_id))
    assert str(row["folder_id"]) == str(folder_id), "folder_id must survive soft delete"

    client.post(f"/documents/{doc_id}/restore", headers=headers)

    row_after = _get_doc_from_db(uuid.UUID(doc_id))
    assert row_after["deleted_at"] is None
    assert str(row_after["folder_id"]) == str(folder_id), "folder_id must survive restore"


def test_restore_nonexistent_returns_404(client, firm_a_owner):
    r = client.post(f"/documents/{uuid.uuid4()}/restore", headers=firm_a_owner["headers"])
    assert r.status_code == 404


def test_restore_live_doc_returns_404(client, firm_a_owner):
    """Restoring a doc that is not in trash returns 404."""
    headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, headers)
    doc_id = _upload(client, headers, client_id, eng_id)

    r = client.post(f"/documents/{doc_id}/restore", headers=headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 5. Non-trio member refused on delete and restore
# ---------------------------------------------------------------------------

def test_non_admin_member_refused_on_delete(client, firm_a_owner):
    """Regular engagement member (not administrator) gets 404 on delete."""
    firm_id = firm_a_owner["firm_id"]
    owner_headers = firm_a_owner["headers"]

    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)
    doc_id = _upload(client, owner_headers, client_id, eng_id)

    email, password, user_id = _create_user(firm_id)
    _add_member(firm_id, eng_id, user_id, is_administrator=False)
    staff_headers = _login(client, email, password)

    r = client.delete(f"/documents/{doc_id}", headers=staff_headers)
    assert r.status_code == 404


def test_non_admin_member_refused_on_restore(client, firm_a_owner):
    """Regular engagement member cannot restore either."""
    firm_id = firm_a_owner["firm_id"]
    owner_headers = firm_a_owner["headers"]

    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)
    doc_id = _upload(client, owner_headers, client_id, eng_id)
    _soft_delete(client, owner_headers, doc_id)

    email, password, user_id = _create_user(firm_id)
    _add_member(firm_id, eng_id, user_id, is_administrator=False)
    staff_headers = _login(client, email, password)

    r = client.post(f"/documents/{doc_id}/restore", headers=staff_headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 6. Purge refused for manager (owner-only)
# ---------------------------------------------------------------------------

def test_purge_refused_for_manager(client, firm_a_owner):
    """Manager can delete and restore but cannot purge (purge is firm_owner only)."""
    firm_id = firm_a_owner["firm_id"]
    owner_headers = firm_a_owner["headers"]

    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)
    doc_id = _upload(client, owner_headers, client_id, eng_id)
    _soft_delete(client, owner_headers, doc_id)

    email, password, _ = _create_user(firm_id, role=UserRole.manager)
    mgr_headers = _login(client, email, password)

    with patch("app.api.documents.s3_service.delete_object") as mock_del:
        r = client.post(
            f"/documents/{doc_id}/purge",
            json={"confirm": True},
            headers=mgr_headers,
        )
        mock_del.assert_not_called()
    assert r.status_code == 403


def test_purge_all_refused_for_manager(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    owner_headers = firm_a_owner["headers"]

    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)
    doc_id = _upload(client, owner_headers, client_id, eng_id)
    _soft_delete(client, owner_headers, doc_id)

    email, password, _ = _create_user(firm_id, role=UserRole.manager)
    mgr_headers = _login(client, email, password)

    with patch("app.api.documents.s3_service.delete_object") as mock_del:
        r = client.post(
            "/documents/trash/purge-all",
            json={"confirm": True},
            headers=mgr_headers,
        )
        mock_del.assert_not_called()
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# 7. Purge refused without confirm=true
# ---------------------------------------------------------------------------

def test_purge_without_confirm_refused(client, firm_a_owner):
    """Purge with confirm=false must be refused without touching S3 or DB."""
    owner_headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)
    doc_id = _upload(client, owner_headers, client_id, eng_id)
    _soft_delete(client, owner_headers, doc_id)

    with patch("app.api.documents.s3_service.delete_object") as mock_del:
        r = client.post(
            f"/documents/{doc_id}/purge",
            json={"confirm": False},
            headers=owner_headers,
        )
        mock_del.assert_not_called()
    assert r.status_code == 400

    # DB row must still exist.
    row = _get_doc_from_db(uuid.UUID(doc_id))
    assert row is not None, "DB row must survive a refused purge"
    assert row["deleted_at"] is not None, "deleted_at must still be set"


def test_purge_all_without_confirm_refused(client, firm_a_owner):
    owner_headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)
    doc_id = _upload(client, owner_headers, client_id, eng_id)
    _soft_delete(client, owner_headers, doc_id)

    with patch("app.api.documents.s3_service.delete_object") as mock_del:
        r = client.post(
            "/documents/trash/purge-all",
            json={"confirm": False},
            headers=owner_headers,
        )
        mock_del.assert_not_called()
    assert r.status_code == 400

    row = _get_doc_from_db(uuid.UUID(doc_id))
    assert row is not None


# ---------------------------------------------------------------------------
# 8. Real purge: calls delete_object, hard-deletes row
#    THIS IS THE ONLY TEST IN THE DOCUMENTS TEST SUITE THAT EXPECTS delete_object
# ---------------------------------------------------------------------------

def test_purge_permanently_destroys_document(client, firm_a_owner):
    """Confirm call, permanent destruction: delete_object called, DB row gone."""
    owner_headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)
    doc_id = _upload(client, owner_headers, client_id, eng_id)
    _soft_delete(client, owner_headers, doc_id)

    with patch("app.api.documents.s3_service.delete_object") as mock_del:
        r = client.post(
            f"/documents/{doc_id}/purge",
            json={"confirm": True},
            headers=owner_headers,
        )
        assert r.status_code == 204, r.text
        mock_del.assert_called_once()

    # DB row must be gone (hard deleted).
    row = _get_doc_from_db(uuid.UUID(doc_id))
    assert row is None, "DB row must be hard-deleted after purge"


def test_purge_live_document_returns_404(client, firm_a_owner):
    """Purging a document that is not in trash (not soft-deleted) returns 404."""
    owner_headers = firm_a_owner["headers"]
    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)
    doc_id = _upload(client, owner_headers, client_id, eng_id)

    with patch("app.api.documents.s3_service.delete_object") as mock_del:
        r = client.post(
            f"/documents/{doc_id}/purge",
            json={"confirm": True},
            headers=owner_headers,
        )
        mock_del.assert_not_called()
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 9. purge-all respects scope boundary
# ---------------------------------------------------------------------------

def test_purge_all_respects_engagement_scope(client, firm_a_owner):
    """purge-all scoped to engagement A must not destroy engagement B's trash."""
    owner_headers = firm_a_owner["headers"]

    # Create two engagements under the same client.
    cl = client.post("/clients/", json={"name": "Scope Client"}, headers=owner_headers)
    client_id = cl.json()["id"]

    eng_a = client.post(
        "/engagements/", json={"name": "Eng A", "client_id": client_id}, headers=owner_headers
    )
    eng_a_id = eng_a.json()["id"]

    eng_b = client.post(
        "/engagements/", json={"name": "Eng B", "client_id": client_id}, headers=owner_headers
    )
    eng_b_id = eng_b.json()["id"]

    doc_a_id = _upload(client, owner_headers, client_id, eng_a_id, filename="a.txt")
    doc_b_id = _upload(client, owner_headers, client_id, eng_b_id, filename="b.txt")

    _soft_delete(client, owner_headers, doc_a_id)
    _soft_delete(client, owner_headers, doc_b_id)

    with patch("app.api.documents.s3_service.delete_object") as mock_del:
        r = client.post(
            "/documents/trash/purge-all",
            json={"confirm": True, "scope": "engagement", "engagement_id": eng_a_id},
            headers=owner_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["purged"] == 1
        mock_del.assert_called_once()

    # Eng A doc is gone from DB.
    assert _get_doc_from_db(uuid.UUID(doc_a_id)) is None

    # Eng B doc still exists in DB (still in trash).
    assert _get_doc_from_db(uuid.UUID(doc_b_id)) is not None
