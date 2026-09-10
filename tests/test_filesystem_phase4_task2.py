# tests/test_filesystem_phase4_task2.py
"""
Guard tests for Filesystem Phase 4 Task 2: rename, move, copy.

Tests:
  1. test_rename_succeeds_for_member
  2. test_rename_refused_for_non_member
  3. test_move_within_engagement_succeeds_for_general_member
  4. test_move_into_wrong_engagement_folder_refused
  5. test_move_across_engagements_refused_for_non_trio
  6. test_move_across_engagements_succeeds_for_trio_with_audit
  7. test_copy_in_place_creates_distinct_document
  8. test_copy_across_same_client_different_engagement
  9. test_copy_across_different_clients
  10. test_copy_source_revoked_mid_flight
  11. test_copy_into_destination_with_same_name_triggers_conflict
"""

import io
import uuid
from unittest.mock import patch

import pytest

from tests.conftest import TestingSessionLocal
from app.models.user import User
from app.models.document import Document
from app.models.document_folder import DocumentFolder
from app.models.engagement_member import EngagementMember
from app.core.enums import UserRole
from app.core.security import get_password_hash


# ---------------------------------------------------------------------------
# Helpers (mirror test_filesystem_phase4_task1.py)
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


def _create_folder(firm_id, scope, client_id=None, engagement_id=None):
    """Create a DocumentFolder row directly via TestingSessionLocal."""
    db = TestingSessionLocal()
    try:
        folder = DocumentFolder(
            firm_id=firm_id,
            scope=scope,
            name=f"Folder-{uuid.uuid4()}",
            client_id=client_id,
            engagement_id=engagement_id,
        )
        db.add(folder)
        db.commit()
        db.refresh(folder)
        folder_id = str(folder.id)
    finally:
        db.close()
    return folder_id


# ---------------------------------------------------------------------------
# 1. test_rename_succeeds_for_member
# ---------------------------------------------------------------------------

def test_rename_succeeds_for_member(client, firm_a_owner):
    """A member of the engagement can rename a document in it."""
    owner_headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]
    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)

    doc_id = _upload(client, owner_headers, client_id, eng_id, filename="original.txt")

    email, password, user_id = _create_user(firm_id, role=UserRole.staff)
    _add_member(firm_id, eng_id, user_id)
    member_headers = _login(client, email, password)

    r = client.patch(
        f"/documents/{doc_id}/rename",
        json={"filename": "renamed.txt"},
        headers=member_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["filename"] == "renamed.txt"


# ---------------------------------------------------------------------------
# 2. test_rename_refused_for_non_member
# ---------------------------------------------------------------------------

def test_rename_refused_for_non_member(client, firm_a_owner):
    """A staff user who is NOT a member of the engagement cannot rename documents."""
    owner_headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]
    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)

    doc_id = _upload(client, owner_headers, client_id, eng_id, filename="original.txt")

    email, password, _ = _create_user(firm_id, role=UserRole.staff)
    non_member_headers = _login(client, email, password)

    r = client.patch(
        f"/documents/{doc_id}/rename",
        json={"filename": "hacked.txt"},
        headers=non_member_headers,
    )
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# 3. test_move_within_engagement_succeeds_for_general_member
# ---------------------------------------------------------------------------

def test_move_within_engagement_succeeds_for_general_member(client, firm_a_owner):
    """A regular engagement member (not admin) can move a doc within their engagement."""
    owner_headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]
    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)

    doc_id = _upload(client, owner_headers, client_id, eng_id, filename="doc.txt")

    folder_id = _create_folder(firm_id, "engagement", client_id=client_id, engagement_id=eng_id)

    email, password, user_id = _create_user(firm_id, role=UserRole.staff)
    _add_member(firm_id, eng_id, user_id)
    member_headers = _login(client, email, password)

    r = client.patch(
        f"/documents/{doc_id}/move",
        json={"folder_id": folder_id},
        headers=member_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["folder_id"] is not None


# ---------------------------------------------------------------------------
# 4. test_move_into_wrong_engagement_folder_refused
# ---------------------------------------------------------------------------

def test_move_into_wrong_engagement_folder_refused(client, firm_a_owner):
    """Moving a doc from engagement A into a folder belonging to engagement B is refused (400)."""
    owner_headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]

    client_id_a, eng_id_a = _setup_client_and_engagement(client, owner_headers)
    client_id_b, eng_id_b = _setup_client_and_engagement(client, owner_headers)

    doc_id = _upload(client, owner_headers, client_id_a, eng_id_a, filename="doc.txt")

    # Folder belongs to engagement B.
    folder_id = _create_folder(firm_id, "engagement", client_id=client_id_b, engagement_id=eng_id_b)

    # Use owner (who can see all documents) to attempt the move, supplying only folder_id
    # (not engagement_id), so it takes the within-scope path.
    r = client.patch(
        f"/documents/{doc_id}/move",
        json={"folder_id": folder_id},
        headers=owner_headers,
    )
    assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# 5. test_move_across_engagements_refused_for_non_trio
# ---------------------------------------------------------------------------

def test_move_across_engagements_refused_for_non_trio(client, firm_a_owner):
    """A plain engagement member (not admin/manager/owner) cannot move across engagements."""
    owner_headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]

    client_id_a, eng_id_a = _setup_client_and_engagement(client, owner_headers)
    client_id_b, eng_id_b = _setup_client_and_engagement(client, owner_headers)

    doc_id = _upload(client, owner_headers, client_id_a, eng_id_a, filename="doc.txt")

    email, password, user_id = _create_user(firm_id, role=UserRole.staff)
    _add_member(firm_id, eng_id_a, user_id, is_administrator=False)
    member_headers = _login(client, email, password)

    r = client.patch(
        f"/documents/{doc_id}/move",
        json={
            "engagement_id": eng_id_b,
            "client_id": client_id_b,
        },
        headers=member_headers,
    )
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# 6. test_move_across_engagements_succeeds_for_trio_with_audit
# ---------------------------------------------------------------------------

def test_move_across_engagements_succeeds_for_trio_with_audit(client, firm_a_owner):
    """An engagement administrator can move a doc across engagements.
    The move is logged with from/to engagement_id in the log_event metadata.
    """
    owner_headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]

    client_id_a, eng_id_a = _setup_client_and_engagement(client, owner_headers)
    client_id_b, eng_id_b = _setup_client_and_engagement(client, owner_headers)

    doc_id = _upload(client, owner_headers, client_id_a, eng_id_a, filename="doc.txt")

    email, password, user_id = _create_user(firm_id, role=UserRole.staff)
    _add_member(firm_id, eng_id_a, user_id, is_administrator=True)
    admin_headers = _login(client, email, password)

    with patch("app.services.document_service.log_event") as mock_log:
        r = client.patch(
            f"/documents/{doc_id}/move",
            json={
                "engagement_id": eng_id_b,
                "client_id": client_id_b,
            },
            headers=admin_headers,
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["engagement_id"] == eng_id_b

    # Verify log_event was called with from/to engagement IDs.
    copy_calls = [
        c for c in mock_log.call_args_list
        if c.kwargs.get("event_type") == "document.moved_across_engagements"
    ]
    assert len(copy_calls) == 1, f"Expected 1 move_across call, got {len(copy_calls)}"
    meta = copy_calls[0].kwargs["metadata"]
    assert meta["from_engagement_id"] == eng_id_a
    assert meta["to_engagement_id"] == eng_id_b


# ---------------------------------------------------------------------------
# 7. test_copy_in_place_creates_distinct_document
# ---------------------------------------------------------------------------

def test_copy_in_place_creates_distinct_document(client, firm_a_owner):
    """Copying a doc in-place creates a new Document row with a different id,
    same content, and copied_from_document_id pointing at the source.
    Uses duplicate_action='keep_both' because copying in-place finds the source
    as a duplicate (same filename, same folder), which is expected behavior.
    """
    owner_headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]
    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)

    src_doc_id = _upload(client, owner_headers, client_id, eng_id, filename="original.txt")

    with patch("app.services.s3.copy_object_within_bucket"):
        r = client.post(
            f"/documents/{src_doc_id}/copy",
            json={"duplicate_action": "keep_both"},
            headers=owner_headers,
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["document"] is not None
    new_doc = body["document"]

    assert new_doc["id"] != src_doc_id
    # keep_both appends (2) to the copy's filename.
    assert new_doc["filename"] == "original (2).txt"
    assert new_doc["copied_from_document_id"] == src_doc_id

    # Original must still be live.
    db = TestingSessionLocal()
    try:
        src = db.query(Document).filter(Document.id == src_doc_id).first()
        assert src is not None
        assert src.deleted_at is None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 8. test_copy_across_same_client_different_engagement
# ---------------------------------------------------------------------------

def test_copy_across_same_client_different_engagement(client, firm_a_owner):
    """Copying a doc to a folder in a different engagement (same client) places it there
    and sets copied_from_document_id correctly.
    """
    owner_headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]

    # Both engagements under the same client.
    cl = client.post("/clients/", json={"name": f"Client-{uuid.uuid4()}"}, headers=owner_headers)
    assert cl.status_code == 201
    client_id = cl.json()["id"]

    eng_a = client.post(
        "/engagements/",
        json={"name": f"Eng-A-{uuid.uuid4()}", "client_id": client_id},
        headers=owner_headers,
    )
    assert eng_a.status_code == 201
    eng_id_a = eng_a.json()["id"]

    eng_b = client.post(
        "/engagements/",
        json={"name": f"Eng-B-{uuid.uuid4()}", "client_id": client_id},
        headers=owner_headers,
    )
    assert eng_b.status_code == 201
    eng_id_b = eng_b.json()["id"]

    src_doc_id = _upload(client, owner_headers, client_id, eng_id_a, filename="form.pdf")

    # Create a folder in engagement B.
    dest_folder_id = _create_folder(firm_id, "engagement", client_id=client_id, engagement_id=eng_id_b)

    with patch("app.services.s3.copy_object_within_bucket"):
        r = client.post(
            f"/documents/{src_doc_id}/copy",
            json={"folder_id": dest_folder_id},
            headers=owner_headers,
        )

    assert r.status_code == 200, r.text
    new_doc = r.json()["document"]
    assert new_doc is not None
    assert new_doc["engagement_id"] == eng_id_b
    assert new_doc["copied_from_document_id"] == src_doc_id

    # Source unchanged.
    db = TestingSessionLocal()
    try:
        src = db.query(Document).filter(Document.id == src_doc_id).first()
        assert src is not None
        assert str(src.engagement_id) == eng_id_a
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 9. test_copy_across_different_clients
# ---------------------------------------------------------------------------

def test_copy_across_different_clients(client, firm_a_owner):
    """Copying across clients sets cross_client=True in the behavioral event metadata."""
    owner_headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]

    client_x_id, eng_x_id = _setup_client_and_engagement(client, owner_headers)
    client_y_id, eng_y_id = _setup_client_and_engagement(client, owner_headers)

    src_doc_id = _upload(client, owner_headers, client_x_id, eng_x_id, filename="cross.pdf")

    dest_folder_id = _create_folder(firm_id, "engagement", client_id=client_y_id, engagement_id=eng_y_id)

    with patch("app.services.s3.copy_object_within_bucket"):
        with patch("app.services.document_service.log_event") as mock_log:
            r = client.post(
                f"/documents/{src_doc_id}/copy",
                json={"folder_id": dest_folder_id},
                headers=owner_headers,
            )

    assert r.status_code == 200, r.text
    assert r.json()["document"] is not None

    # Find the document.copied event and check cross_client=True.
    copy_calls = [
        c for c in mock_log.call_args_list
        if c.kwargs.get("event_type") == "document.copied"
    ]
    assert len(copy_calls) == 1, f"Expected 1 copy event, got {len(copy_calls)}"
    meta = copy_calls[0].kwargs["metadata"]
    assert meta["cross_client"] is True, f"Expected cross_client=True, got {meta['cross_client']}"


# ---------------------------------------------------------------------------
# 10. test_copy_source_revoked_mid_flight
# ---------------------------------------------------------------------------

def test_copy_source_revoked_mid_flight(client, firm_a_owner):
    """If the caller's membership is revoked between the UI load and the copy call,
    the copy endpoint returns 404 (source access denied).
    """
    owner_headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]
    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)

    # Upload as owner.
    src_doc_id = _upload(client, owner_headers, client_id, eng_id, filename="secret.txt")

    # Create staff member.
    email, password, user_id = _create_user(firm_id, role=UserRole.staff)
    _add_member(firm_id, eng_id, user_id)
    member_headers = _login(client, email, password)

    # Revoke membership.
    db = TestingSessionLocal()
    try:
        member = db.query(EngagementMember).filter(
            EngagementMember.firm_id == firm_id,
            EngagementMember.engagement_id == eng_id,
            EngagementMember.user_id == uuid.UUID(user_id),
        ).first()
        assert member is not None
        db.delete(member)
        db.commit()
    finally:
        db.close()

    with patch("app.services.s3.copy_object_within_bucket") as mock_copy:
        r = client.post(
            f"/documents/{src_doc_id}/copy",
            json={},
            headers=member_headers,
        )
        # S3 copy must never be called -- access denied before any S3 interaction.
        mock_copy.assert_not_called()

    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# 11. test_copy_into_destination_with_same_name_triggers_conflict
# ---------------------------------------------------------------------------

def test_copy_into_destination_with_same_name_triggers_conflict(client, firm_a_owner):
    """Copying a doc when the destination already has a doc with the same filename
    returns a conflict dict and does not create a new document row.
    """
    owner_headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]

    client_id, eng_id_a = _setup_client_and_engagement(client, owner_headers)

    # Second engagement under same client.
    cl_resp = client.get(f"/clients/{client_id}", headers=owner_headers)
    eng_b = client.post(
        "/engagements/",
        json={"name": f"Eng-B-{uuid.uuid4()}", "client_id": client_id},
        headers=owner_headers,
    )
    assert eng_b.status_code == 201
    eng_id_b = eng_b.json()["id"]

    # Upload same filename in both engagements.
    src_doc_id = _upload(client, owner_headers, client_id, eng_id_a, filename="report.pdf")
    dest_folder_id = _create_folder(firm_id, "engagement", client_id=client_id, engagement_id=eng_id_b)
    _upload(client, owner_headers, client_id, eng_id_b, filename="report.pdf")

    # Assign existing doc in eng_b to the dest folder.
    db = TestingSessionLocal()
    try:
        existing = db.query(Document).filter(
            Document.engagement_id == eng_id_b,
            Document.filename == "report.pdf",
            Document.deleted_at.is_(None),
        ).first()
        assert existing is not None
        existing.folder_id = dest_folder_id
        db.commit()
    finally:
        db.close()

    with patch("app.services.s3.copy_object_within_bucket") as mock_copy:
        r = client.post(
            f"/documents/{src_doc_id}/copy",
            json={"folder_id": dest_folder_id},
            headers=owner_headers,
        )
        mock_copy.assert_not_called()

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["document"] is None, f"Expected no document on conflict, got {body['document']}"
    assert body["conflict"] is not None
    assert body["conflict"]["filename"] == "report.pdf"


# ---------------------------------------------------------------------------
# 12. test_copy_to_firm_library_folder_requires_manager_or_owner
# ---------------------------------------------------------------------------

def test_copy_to_firm_library_folder_requires_manager_or_owner(client, firm_a_owner):
    """Plain staff member is denied 403 when copying to a firm_library-scoped folder.
    A manager or firm owner performing the same copy succeeds.

    This guards the authorization gap identified in Phase 6 discovery (D9):
    assert_can_write_to_destination previously returned for any staff member when
    dest_scope == "firm_library", allowing unauthorized writes to the Firm Library.
    This matches the failure pattern in CVE-2026-9248 and CVE-2026-73612, where
    copy/duplicate endpoints authorize on source access but not destination sensitivity.
    """
    firm_id = firm_a_owner["firm_id"]
    owner_headers = firm_a_owner["headers"]

    client_id, eng_id = _setup_client_and_engagement(client, owner_headers)
    src_doc_id = _upload(client, owner_headers, client_id, eng_id, filename="policy.pdf")

    # Create a firm_library-scoped destination folder (no client or engagement).
    firm_lib_folder_id = _create_folder(firm_id, "firm_library")

    # Plain staff member who CAN read the source (they are a member of the engagement).
    email, password, user_id = _create_user(firm_id, role=UserRole.staff)
    _add_member(firm_id, eng_id, user_id)
    staff_headers = _login(client, email, password)

    # Staff must be refused with 403 -- source access is not sufficient for
    # firm_library destination writes.
    with patch("app.services.s3.copy_object_within_bucket"):
        r_staff = client.post(
            f"/documents/{src_doc_id}/copy",
            json={"folder_id": firm_lib_folder_id},
            headers=staff_headers,
        )

    assert r_staff.status_code == 403, (
        f"Non-elevated staff must be denied 403 on firm_library copy; got {r_staff.status_code}: {r_staff.text}"
    )

    # Owner must succeed.
    with patch("app.services.s3.copy_object_within_bucket"):
        r_owner = client.post(
            f"/documents/{src_doc_id}/copy",
            json={"folder_id": firm_lib_folder_id},
            headers=owner_headers,
        )

    assert r_owner.status_code == 200, (
        f"Firm owner must succeed on firm_library copy; got {r_owner.status_code}: {r_owner.text}"
    )
    new_doc = r_owner.json().get("document")
    assert new_doc is not None, "Expected a document in the response body"
    assert new_doc["copied_from_document_id"] == src_doc_id
