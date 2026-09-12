# tests/test_filesystem_phase7_task1.py
"""
Guard tests for Filesystem Phase 7 Task 1: engagement finalize/lock.

Spec reference: Filesystem Build Specification, Sections 12, 15, 17.

Tests:
  1. Finalize sets finalized_at and finalized_by on the engagement.
  2. Unfinalize clears finalized_at and finalized_by.
  3. Every document mutation endpoint returns 422 on a finalized engagement.
  4. Download (GET /documents/{id}/download) succeeds on a finalized engagement.
  5. Non-trio engagement member is refused 422 on finalize and unfinalize.
  6. Finalize and unfinalize are both audit-logged.
  7. Finalizing an already-finalized engagement is a 200 no-op (idempotent).
  8. Unfinalizing an already-open engagement is a 200 no-op (idempotent).
  9. Folder create and rename are refused 422 on a finalized engagement.
"""

import io
import uuid
from unittest.mock import patch

from app.models.document import Document
from app.models.engagement import Engagement
from app.models.engagement_member import EngagementMember
from app.core.enums import UserRole
from app.core.security import get_password_hash
from app.models.audit_log import AuditLog
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


def _setup_client_and_engagement(test_client, headers):
    cl = test_client.post(
        "/clients/", json={"name": f"Client-{uuid.uuid4()}"}, headers=headers
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


def _finalize(test_client, headers, engagement_id):
    r = test_client.post(f"/engagements/{engagement_id}/finalize", headers=headers)
    assert r.status_code == 200, f"Finalize failed: {r.text}"
    return r


def _get_engagement_from_db(engagement_id):
    db = TestingSessionLocal()
    try:
        eng = db.query(Engagement).filter(Engagement.id == engagement_id).first()
        return {
            "finalized_at": eng.finalized_at,
            "finalized_by": str(eng.finalized_by) if eng.finalized_by else None,
        }
    finally:
        db.close()


def _count_audit_entries(entity_id, action):
    db = TestingSessionLocal()
    try:
        return db.query(AuditLog).filter(
            AuditLog.entity_id == entity_id,
            AuditLog.action == action,
        ).count()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1. Finalize sets finalized_at and finalized_by
# ---------------------------------------------------------------------------

class TestFinalizeSetFields:

    def test_finalize_sets_finalized_at_and_finalized_by(self, client, firm_a_owner):
        headers = firm_a_owner["headers"]
        # Get owner identity from the me endpoint.
        me_r = client.get("/auth/me", headers=headers)
        owner_id = me_r.json()["id"] if me_r.status_code == 200 else None
        _, eng_id = _setup_client_and_engagement(client, headers)

        r = client.post(f"/engagements/{eng_id}/finalize", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["finalized_at"] is not None
        if owner_id:
            assert r.json()["finalized_by"] == owner_id

        row = _get_engagement_from_db(uuid.UUID(eng_id))
        assert row["finalized_at"] is not None, "finalized_at must be set in DB"
        assert row["finalized_by"] is not None, "finalized_by must be set in DB"


# ---------------------------------------------------------------------------
# 2. Unfinalize clears finalized_at and finalized_by
# ---------------------------------------------------------------------------

class TestUnfinalizeClears:

    def test_unfinalize_clears_finalized_fields(self, client, firm_a_owner):
        headers = firm_a_owner["headers"]
        _, eng_id = _setup_client_and_engagement(client, headers)

        _finalize(client, headers, eng_id)

        r = client.post(f"/engagements/{eng_id}/unfinalize", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["finalized_at"] is None
        assert r.json()["finalized_by"] is None

        row = _get_engagement_from_db(uuid.UUID(eng_id))
        assert row["finalized_at"] is None, "finalized_at must be cleared"
        assert row["finalized_by"] is None, "finalized_by must be cleared"


# ---------------------------------------------------------------------------
# 3. Document mutation endpoints return 422 on finalized engagement
# ---------------------------------------------------------------------------

class TestMutationsRefusedWhenFinalized:

    def test_upload_refused_on_finalized(self, client, firm_a_owner):
        """POST /documents/upload returns 422 on a finalized engagement.

        Watched-fail: removing the finalize check in upload_document makes this
        return 201 instead of 422, then restoring the check goes green.
        """
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)
        _finalize(client, headers, eng_id)

        with patch("app.api.documents.s3_service.upload_fileobj"):
            r = client.post(
                f"/documents/upload?client_id={client_id}&engagement_id={eng_id}",
                files={"file": ("blocked.txt", io.BytesIO(b"x"), "text/plain")},
                headers=headers,
            )
        assert r.status_code == 422, (
            f"Upload on finalized engagement must return 422; got {r.status_code}: {r.text}"
        )
        assert "finalized" in r.json()["detail"].lower()

    def test_rename_refused_on_finalized(self, client, firm_a_owner):
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)
        doc_id = _upload_staff(client, headers, client_id, eng_id)
        _finalize(client, headers, eng_id)

        r = client.patch(
            f"/documents/{doc_id}/rename",
            json={"new_filename": "renamed.txt"},
            headers=headers,
        )
        assert r.status_code == 422, (
            f"Rename on finalized engagement must return 422; got {r.status_code}: {r.text}"
        )

    def test_soft_delete_refused_on_finalized(self, client, firm_a_owner):
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)
        doc_id = _upload_staff(client, headers, client_id, eng_id)
        _finalize(client, headers, eng_id)

        r = client.delete(f"/documents/{doc_id}", headers=headers)
        assert r.status_code == 422, (
            f"Delete on finalized engagement must return 422; got {r.status_code}: {r.text}"
        )

    def test_restore_refused_on_finalized(self, client, firm_a_owner):
        """Restore from trash is refused on a finalized engagement.

        Setup: upload, delete (before finalizing), then finalize, then attempt restore.
        """
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)
        doc_id = _upload_staff(client, headers, client_id, eng_id)

        # Delete before finalizing so the doc is in trash.
        r_del = client.delete(f"/documents/{doc_id}", headers=headers)
        assert r_del.status_code == 204

        _finalize(client, headers, eng_id)

        r = client.post(f"/documents/{doc_id}/restore", headers=headers)
        assert r.status_code == 422, (
            f"Restore on finalized engagement must return 422; got {r.status_code}: {r.text}"
        )

    def test_share_to_portal_refused_on_finalized(self, client, firm_a_owner):
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)
        doc_id = _upload_staff(client, headers, client_id, eng_id)
        _finalize(client, headers, eng_id)

        r = client.post(f"/documents/{doc_id}/share-to-portal", headers=headers)
        assert r.status_code == 422, (
            f"Share-to-portal on finalized engagement must return 422; got {r.status_code}: {r.text}"
        )

    def test_unshare_from_portal_refused_on_finalized(self, client, firm_a_owner):
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)
        doc_id = _upload_staff(client, headers, client_id, eng_id)

        # Share before finalizing.
        client.post(f"/documents/{doc_id}/share-to-portal", headers=headers)
        _finalize(client, headers, eng_id)

        r = client.post(f"/documents/{doc_id}/unshare-from-portal", headers=headers)
        assert r.status_code == 422, (
            f"Unshare-from-portal on finalized engagement must return 422; got {r.status_code}: {r.text}"
        )

    def test_create_folder_refused_on_finalized(self, client, firm_a_owner):
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)
        _finalize(client, headers, eng_id)

        r = client.post(
            "/document-folders/",
            json={
                "scope": "engagement",
                "name": "Blocked Folder",
                "client_id": client_id,
                "engagement_id": eng_id,
            },
            headers=headers,
        )
        assert r.status_code == 422, (
            f"Create folder on finalized engagement must return 422; got {r.status_code}: {r.text}"
        )

    def test_rename_folder_refused_on_finalized(self, client, firm_a_owner):
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)

        # Create folder before finalizing.
        r_folder = client.post(
            "/document-folders/",
            json={
                "scope": "engagement",
                "name": "Original Name",
                "client_id": client_id,
                "engagement_id": eng_id,
            },
            headers=headers,
        )
        assert r_folder.status_code == 201, r_folder.text
        folder_id = r_folder.json()["id"]

        _finalize(client, headers, eng_id)

        r = client.patch(
            f"/document-folders/{folder_id}",
            json={"name": "New Name"},
            headers=headers,
        )
        assert r.status_code == 422, (
            f"Rename folder on finalized engagement must return 422; got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# 4. Download still permitted on finalized engagement
# ---------------------------------------------------------------------------

class TestReadPermittedWhenFinalized:

    def test_download_succeeds_on_finalized(self, client, firm_a_owner):
        """GET /documents/{id}/download must succeed on a finalized engagement.

        Spec Section 12: read, preview, download, copy-out, and export remain
        fully open after finalize.
        """
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)
        doc_id = _upload_staff(client, headers, client_id, eng_id)
        _finalize(client, headers, eng_id)

        with patch("app.api.documents.s3_service.generate_presigned_url", return_value="https://s3.example.com/signed"):
            r = client.get(f"/documents/{doc_id}/download", headers=headers)
        assert r.status_code == 200, (
            f"Download must succeed on finalized engagement; got {r.status_code}: {r.text}"
        )

    def test_get_document_succeeds_on_finalized(self, client, firm_a_owner):
        """GET /documents/{id} must succeed on a finalized engagement."""
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)
        doc_id = _upload_staff(client, headers, client_id, eng_id)
        _finalize(client, headers, eng_id)

        r = client.get(f"/documents/{doc_id}", headers=headers)
        assert r.status_code == 200, (
            f"GET document must succeed on finalized engagement; got {r.status_code}: {r.text}"
        )

    def test_list_documents_succeeds_on_finalized(self, client, firm_a_owner):
        """GET /documents must succeed on a finalized engagement."""
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)
        _upload_staff(client, headers, client_id, eng_id)
        _finalize(client, headers, eng_id)

        r = client.get(f"/documents?engagement_id={eng_id}", headers=headers)
        assert r.status_code == 200, (
            f"List documents must succeed on finalized engagement; got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# 5. Non-trio member is refused 422 on finalize/unfinalize
# ---------------------------------------------------------------------------

class TestTrioEnforcement:

    def test_non_trio_member_refused_422_on_finalize(self, client, firm_a_owner):
        """Regular engagement member (not administrator/manager/owner) gets 422 on finalize.

        Watched-fail: removing the assert_can_finalize_engagement call makes
        this return 200 instead of 422, then restoring goes green.
        """
        firm_id = firm_a_owner["firm_id"]
        owner_headers = firm_a_owner["headers"]
        _, eng_id = _setup_client_and_engagement(client, owner_headers)

        email, password, user_id = _create_user(firm_id, role=UserRole.staff)
        _add_member(firm_id, eng_id, user_id, is_administrator=False)
        staff_headers = _login(client, email, password)

        r = client.post(f"/engagements/{eng_id}/finalize", headers=staff_headers)
        assert r.status_code == 422, (
            f"Non-trio member must get 422 on finalize; got {r.status_code}: {r.text}"
        )

    def test_non_trio_member_refused_422_on_unfinalize(self, client, firm_a_owner):
        firm_id = firm_a_owner["firm_id"]
        owner_headers = firm_a_owner["headers"]
        _, eng_id = _setup_client_and_engagement(client, owner_headers)
        _finalize(client, owner_headers, eng_id)

        email, password, user_id = _create_user(firm_id, role=UserRole.staff)
        _add_member(firm_id, eng_id, user_id, is_administrator=False)
        staff_headers = _login(client, email, password)

        r = client.post(f"/engagements/{eng_id}/unfinalize", headers=staff_headers)
        assert r.status_code == 422, (
            f"Non-trio member must get 422 on unfinalize; got {r.status_code}: {r.text}"
        )

    def test_engagement_admin_can_finalize(self, client, firm_a_owner):
        """Engagement administrator is in the trio and must succeed."""
        firm_id = firm_a_owner["firm_id"]
        owner_headers = firm_a_owner["headers"]
        _, eng_id = _setup_client_and_engagement(client, owner_headers)

        email, password, user_id = _create_user(firm_id, role=UserRole.staff)
        _add_member(firm_id, eng_id, user_id, is_administrator=True)
        admin_headers = _login(client, email, password)

        r = client.post(f"/engagements/{eng_id}/finalize", headers=admin_headers)
        assert r.status_code == 200, (
            f"Engagement administrator must succeed on finalize; got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# 6. Finalize and unfinalize are audit-logged
# ---------------------------------------------------------------------------

class TestAuditLogging:

    def test_finalize_writes_audit_log(self, client, firm_a_owner):
        headers = firm_a_owner["headers"]
        _, eng_id = _setup_client_and_engagement(client, headers)
        eng_uuid = uuid.UUID(eng_id)

        count_before = _count_audit_entries(eng_uuid, "engagement.finalized")
        client.post(f"/engagements/{eng_id}/finalize", headers=headers)
        count_after = _count_audit_entries(eng_uuid, "engagement.finalized")

        assert count_after == count_before + 1, (
            f"Finalize must write 1 audit entry; got {count_after - count_before}"
        )

    def test_unfinalize_writes_audit_log(self, client, firm_a_owner):
        headers = firm_a_owner["headers"]
        _, eng_id = _setup_client_and_engagement(client, headers)
        eng_uuid = uuid.UUID(eng_id)

        _finalize(client, headers, eng_id)

        count_before = _count_audit_entries(eng_uuid, "engagement.unfinalized")
        client.post(f"/engagements/{eng_id}/unfinalize", headers=headers)
        count_after = _count_audit_entries(eng_uuid, "engagement.unfinalized")

        assert count_after == count_before + 1, (
            f"Unfinalize must write 1 audit entry; got {count_after - count_before}"
        )


# ---------------------------------------------------------------------------
# 7 & 8. Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:

    def test_finalize_already_finalized_is_200_no_op(self, client, firm_a_owner):
        """Finalizing an already-finalized engagement returns 200 and does not error.

        Matching the share-to-portal precedent: repeated calls succeed silently.
        """
        headers = firm_a_owner["headers"]
        _, eng_id = _setup_client_and_engagement(client, headers)

        r1 = client.post(f"/engagements/{eng_id}/finalize", headers=headers)
        assert r1.status_code == 200, r1.text
        first_finalized_at = r1.json()["finalized_at"]

        r2 = client.post(f"/engagements/{eng_id}/finalize", headers=headers)
        assert r2.status_code == 200, (
            f"Re-finalizing must return 200; got {r2.status_code}: {r2.text}"
        )
        # finalized_at must not change on repeat call
        assert r2.json()["finalized_at"] == first_finalized_at, (
            "Re-finalizing must not change finalized_at"
        )

    def test_unfinalize_already_open_is_200_no_op(self, client, firm_a_owner):
        """Unfinalizing an already-open engagement returns 200 and does not error."""
        headers = firm_a_owner["headers"]
        _, eng_id = _setup_client_and_engagement(client, headers)

        r = client.post(f"/engagements/{eng_id}/unfinalize", headers=headers)
        assert r.status_code == 200, (
            f"Unfinalizing an open engagement must return 200; got {r.status_code}: {r.text}"
        )
        assert r.json()["finalized_at"] is None

    def test_mutations_allowed_after_unfinalize(self, client, firm_a_owner):
        """After unfinalizing, document uploads succeed again."""
        headers = firm_a_owner["headers"]
        client_id, eng_id = _setup_client_and_engagement(client, headers)
        _finalize(client, headers, eng_id)

        # Confirm blocked.
        with patch("app.api.documents.s3_service.upload_fileobj"):
            r_blocked = client.post(
                f"/documents/upload?client_id={client_id}&engagement_id={eng_id}",
                files={"file": ("b.txt", io.BytesIO(b"x"), "text/plain")},
                headers=headers,
            )
        assert r_blocked.status_code == 422

        # Unfinalize.
        client.post(f"/engagements/{eng_id}/unfinalize", headers=headers)

        # Now allowed.
        with patch("app.api.documents.s3_service.upload_fileobj"):
            r_allowed = client.post(
                f"/documents/upload?client_id={client_id}&engagement_id={eng_id}",
                files={"file": ("ok.txt", io.BytesIO(b"y"), "text/plain")},
                headers=headers,
            )
        assert r_allowed.status_code == 201, (
            f"Upload must succeed after unfinalize; got {r_allowed.status_code}: {r_allowed.text}"
        )


# ---------------------------------------------------------------------------
# Cross-engagement move into a finalized destination is refused
# ---------------------------------------------------------------------------

class TestMoveIntoFinalizedDestinationRefused:

    def test_move_into_finalized_dest_returns_422(self, client, firm_a_owner):
        """PATCH /documents/{id}/move into a finalized destination engagement must
        return 422.

        Watched-fail: the test is run with only the source-side finalize check
        present (no dest check) and fails with 200 instead of 422, confirming it
        genuinely catches the destination gap. Restoring the dest check makes it
        green.
        """
        headers = firm_a_owner["headers"]

        # Source engagement and document.
        src_client_id, src_eng_id = _setup_client_and_engagement(client, headers)
        doc_id = _upload_staff(client, headers, src_client_id, src_eng_id)

        # Destination engagement (same client so the cross-engagement move is valid).
        dest_eng_r = client.post(
            "/engagements/",
            json={"name": f"Dest-Eng", "client_id": src_client_id},
            headers=headers,
        )
        assert dest_eng_r.status_code == 201, dest_eng_r.text
        dest_eng_id = dest_eng_r.json()["id"]

        # Finalize the DESTINATION engagement only.
        _finalize(client, headers, dest_eng_id)

        # Attempt cross-engagement move INTO the finalized destination.
        r = client.patch(
            f"/documents/{doc_id}/move",
            json={"engagement_id": dest_eng_id, "client_id": src_client_id, "folder_id": None},
            headers=headers,
        )
        assert r.status_code == 422, (
            f"Move into finalized destination must return 422; got {r.status_code}: {r.text}"
        )
        assert "finalized" in r.json()["detail"].lower()

    def test_move_out_of_finalized_source_still_refused(self, client, firm_a_owner):
        """The existing source-side check is not broken by adding the dest check.

        Source engagement is finalized, destination is open. Must still return 422.
        """
        headers = firm_a_owner["headers"]

        src_client_id, src_eng_id = _setup_client_and_engagement(client, headers)
        doc_id = _upload_staff(client, headers, src_client_id, src_eng_id)

        dest_eng_r = client.post(
            "/engagements/",
            json={"name": f"Open-Dest-Eng", "client_id": src_client_id},
            headers=headers,
        )
        assert dest_eng_r.status_code == 201
        dest_eng_id = dest_eng_r.json()["id"]

        # Finalize only the SOURCE.
        _finalize(client, headers, src_eng_id)

        r = client.patch(
            f"/documents/{doc_id}/move",
            json={"engagement_id": dest_eng_id, "client_id": src_client_id, "folder_id": None},
            headers=headers,
        )
        assert r.status_code == 422, (
            f"Move out of finalized source must return 422; got {r.status_code}: {r.text}"
        )
