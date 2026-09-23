# tests/test_recent_document_views.py
"""
Guard tests for the recent_document_views backend.

Tests:
  a. Viewing a document via preview or download records a real row.
     Watched-fail: temporarily comment out record_document_view in the
     endpoint, confirm no row is created, restore, confirm it is.
  b. Viewing the same document twice updates last_viewed_at on the
     existing row rather than creating a second row (upsert, not append).
  c. A user who is not a member of the engagement cannot call
     GET /engagements/{id}/recent-documents (membership gate, 404).
  d. A soft-deleted document never appears in the recent list.
  e. Tenant/engagement isolation: firm B user never sees firm A's items;
     viewing a document in engagement X does not appear under engagement Y.
"""

import io
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import TestingSessionLocal
from app.models.recent_document_view import RecentDocumentView
from app.models.engagement_member import EngagementMember
from app.core.enums import UserRole
from app.core.security import get_password_hash
from app.models.firm import Firm
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm_and_owner(slug: str, client) -> dict:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Firm {slug}", slug=slug, timezone="UTC")
        db.add(firm)
        db.commit()
        db.refresh(firm)
        from app.services.tax_organizer_service import seed_firm_organizer_templates
        seed_firm_organizer_templates(firm_id=firm.id, db=db)
        email = f"owner-{uuid.uuid4().hex[:6]}@{slug}.com"
        owner = User(
            firm_id=firm.id,
            email=email,
            hashed_password=get_password_hash("password123"),
            full_name="Owner",
            role=UserRole.firm_owner,
        )
        db.add(owner)
        db.commit()
        firm_id = str(firm.id)
    finally:
        db.close()
    login = client.post("/auth/token", json={"username": email, "password": "password123"})
    token = login.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "firm_id": firm_id}


def _make_staff_user(firm_id: str, client) -> dict:
    db = TestingSessionLocal()
    try:
        email = f"staff-{uuid.uuid4().hex[:8]}@testfirm.com"
        user = User(
            firm_id=uuid.UUID(firm_id),
            email=email,
            hashed_password=get_password_hash("staffpass"),
            full_name="Staff Member",
            role=UserRole.staff,
        )
        db.add(user)
        db.commit()
        user_id = str(user.id)
    finally:
        db.close()
    login = client.post("/auth/token", json={"username": email, "password": "staffpass"})
    token = login.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "user_id": user_id}


def _setup_client(client, headers, name=None) -> str:
    r = client.post("/clients/", json={"name": name or f"C-{uuid.uuid4().hex[:6]}"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _setup_engagement(client, headers, client_id, name=None) -> str:
    r = client.post(
        "/engagements/",
        json={"name": name or f"E-{uuid.uuid4().hex[:6]}", "client_id": client_id},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _upload_doc(client, headers, client_id: str, engagement_id: str) -> str:
    with patch("app.api.documents.s3_service.upload_fileobj"):
        r = client.post(
            f"/documents/upload?client_id={client_id}&engagement_id={engagement_id}",
            files={"file": ("test.pdf", io.BytesIO(b"pdf content"), "application/pdf")},
            headers=headers,
        )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _add_member(firm_id: str, engagement_id: str, user_id: str):
    db = TestingSessionLocal()
    try:
        m = EngagementMember(
            firm_id=uuid.UUID(firm_id),
            engagement_id=uuid.UUID(engagement_id),
            user_id=uuid.UUID(user_id),
        )
        db.add(m)
        db.commit()
    finally:
        db.close()


def _count_recent_rows(user_id: str, document_id: str) -> int:
    db = TestingSessionLocal()
    try:
        return db.query(RecentDocumentView).filter(
            RecentDocumentView.user_id == uuid.UUID(user_id),
            RecentDocumentView.document_id == uuid.UUID(document_id),
        ).count()
    finally:
        db.close()


def _get_recent_row(user_id: str, document_id: str):
    db = TestingSessionLocal()
    try:
        return db.query(RecentDocumentView).filter(
            RecentDocumentView.user_id == uuid.UUID(user_id),
            RecentDocumentView.document_id == uuid.UUID(document_id),
        ).first()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# a. Preview records a real row
# ---------------------------------------------------------------------------

class TestPreviewRecordsView:

    def test_preview_creates_recent_view_row(self, client, firm_a_owner):
        """Calling GET /documents/{id}/preview creates a RecentDocumentView row.

        Watched-fail procedure: temporarily comment out the record_document_view
        call in the preview endpoint body, run this test, confirm it returns 0
        rows instead of 1. Restore the call, test returns 1 row.
        """
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]

        client_id = _setup_client(client, headers)
        eng_id = _setup_engagement(client, headers, client_id)
        doc_id = _upload_doc(client, headers, client_id, eng_id)

        with (
            patch("app.api.documents.check_preview_eligible", return_value=True),
            patch("app.api.documents.s3_service.generate_presigned_url", return_value="https://s3.example.com/signed"),
        ):
            r = client.get(f"/documents/{doc_id}/preview", headers=headers)
        assert r.status_code == 200, r.text

        db = TestingSessionLocal()
        try:
            total = db.query(RecentDocumentView).filter(
                RecentDocumentView.document_id == uuid.UUID(doc_id),
            ).count()
        finally:
            db.close()
        assert total == 1, f"Expected 1 recent_view row, got {total}"


class TestDownloadRecordsView:

    def test_download_creates_recent_view_row(self, client, firm_a_owner):
        """Calling GET /documents/{id}/download creates a RecentDocumentView row."""
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]

        client_id = _setup_client(client, headers)
        eng_id = _setup_engagement(client, headers, client_id)
        doc_id = _upload_doc(client, headers, client_id, eng_id)

        with (
            patch("app.services.document_service.s3_service.generate_presigned_url", return_value="https://s3.example.com/dl"),
            patch("app.api.documents.s3_service.generate_presigned_url", return_value="https://s3.example.com/dl"),
        ):
            r = client.get(f"/documents/{doc_id}/download", headers=headers)
        assert r.status_code == 200, r.text

        db = TestingSessionLocal()
        try:
            total = db.query(RecentDocumentView).filter(
                RecentDocumentView.document_id == uuid.UUID(doc_id),
            ).count()
        finally:
            db.close()
        assert total == 1, f"Expected 1 recent_view row after download, got {total}"


# ---------------------------------------------------------------------------
# b. Second view updates last_viewed_at, not a second row
# ---------------------------------------------------------------------------

class TestUpsertNotDuplicate:

    def test_second_preview_updates_not_duplicates(self, client, firm_a_owner):
        """Previewing the same document twice updates last_viewed_at on the
        existing row rather than inserting a second row.

        Confirms the upsert on (user_id, document_id) is working correctly.
        """
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]

        client_id = _setup_client(client, headers)
        eng_id = _setup_engagement(client, headers, client_id)
        doc_id = _upload_doc(client, headers, client_id, eng_id)

        preview_kwargs = dict(
            patch_a=patch("app.api.documents.check_preview_eligible", return_value=True),
            patch_b=patch("app.api.documents.s3_service.generate_presigned_url", return_value="https://example.com/1"),
        )

        with (
            patch("app.api.documents.check_preview_eligible", return_value=True),
            patch("app.api.documents.s3_service.generate_presigned_url", return_value="https://example.com/1"),
        ):
            r1 = client.get(f"/documents/{doc_id}/preview", headers=headers)
        assert r1.status_code == 200

        db = TestingSessionLocal()
        try:
            row1 = db.query(RecentDocumentView).filter(
                RecentDocumentView.document_id == uuid.UUID(doc_id),
            ).first()
            lv1 = row1.last_viewed_at if row1 else None
        finally:
            db.close()

        with (
            patch("app.api.documents.check_preview_eligible", return_value=True),
            patch("app.api.documents.s3_service.generate_presigned_url", return_value="https://example.com/2"),
        ):
            r2 = client.get(f"/documents/{doc_id}/preview", headers=headers)
        assert r2.status_code == 200

        db = TestingSessionLocal()
        try:
            count = db.query(RecentDocumentView).filter(
                RecentDocumentView.document_id == uuid.UUID(doc_id),
            ).count()
            row2 = db.query(RecentDocumentView).filter(
                RecentDocumentView.document_id == uuid.UUID(doc_id),
            ).first()
            lv2 = row2.last_viewed_at if row2 else None
        finally:
            db.close()

        assert count == 1, f"Expected exactly 1 row after two previews, got {count}"
        # last_viewed_at must be >= first view (may be equal if within same second)
        if lv1 and lv2:
            assert lv2 >= lv1, "last_viewed_at must not decrease on a second view"


# ---------------------------------------------------------------------------
# c. Non-member staff cannot list recent documents
# ---------------------------------------------------------------------------

class TestMembershipGate:

    def test_non_member_gets_404(self, client, firm_a_owner):
        """A staff user who is not a member of the engagement gets 404 on the
        recent-documents endpoint, matching the access-gate pattern used
        by assert_can_access_document.

        Watched-fail procedure: temporarily remove the membership check from the
        endpoint body, run this test, confirm it returns 200 instead of 404.
        Restore the check, test returns 404.
        """
        firm_id = firm_a_owner["firm_id"]
        owner_headers = firm_a_owner["headers"]

        client_id = _setup_client(client, owner_headers)
        eng_id = _setup_engagement(client, owner_headers, client_id)

        staff = _make_staff_user(firm_id, client)
        # Do NOT add the staff user as a member of the engagement.

        r = client.get(f"/engagements/{eng_id}/recent-documents", headers=staff["headers"])
        assert r.status_code == 404, (
            f"Non-member staff must get 404; got {r.status_code}: {r.text}"
        )

    def test_member_gets_200(self, client, firm_a_owner):
        """A staff user who IS a member of the engagement gets 200."""
        firm_id = firm_a_owner["firm_id"]
        owner_headers = firm_a_owner["headers"]

        client_id = _setup_client(client, owner_headers)
        eng_id = _setup_engagement(client, owner_headers, client_id)

        staff = _make_staff_user(firm_id, client)
        _add_member(firm_id, eng_id, staff["user_id"])

        r = client.get(f"/engagements/{eng_id}/recent-documents", headers=staff["headers"])
        assert r.status_code == 200, (
            f"Member staff must get 200; got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# d. Soft-deleted document does not appear in recent list
# ---------------------------------------------------------------------------

class TestSoftDeleteExclusion:

    def test_deleted_doc_absent_from_recent(self, client, firm_a_owner):
        """A document that is soft-deleted must not appear in the recent list,
        even if a real view was recorded before deletion."""
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]

        client_id = _setup_client(client, headers)
        eng_id = _setup_engagement(client, headers, client_id)
        doc_id = _upload_doc(client, headers, client_id, eng_id)

        # Record a view directly in the DB.
        db = TestingSessionLocal()
        try:
            from app.services.recent_documents_service import record_document_view
            from app.models.firm import Firm
            firm_uuid = uuid.UUID(firm_id)
            me = client.get("/users/me", headers=headers)
            user_id = uuid.UUID(me.json()["id"])
            record_document_view(
                db,
                firm_id=firm_uuid,
                user_id=user_id,
                engagement_id=uuid.UUID(eng_id),
                document_id=uuid.UUID(doc_id),
            )
        finally:
            db.close()

        # Soft-delete the document.
        r_del = client.delete(f"/documents/{doc_id}", headers=headers)
        assert r_del.status_code == 204, r_del.text

        # Recent list must be empty.
        r = client.get(f"/engagements/{eng_id}/recent-documents", headers=headers)
        assert r.status_code == 200, r.text
        items = r.json()
        ids = [item["document_id"] for item in items]
        assert doc_id not in ids, (
            f"Soft-deleted document {doc_id} must not appear in recent list; got {ids}"
        )


# ---------------------------------------------------------------------------
# e. Tenant and engagement isolation
# ---------------------------------------------------------------------------

class TestIsolation:

    def test_firm_b_user_sees_nothing_in_firm_a_engagement(self, client, firm_a_owner, firm_b_owner):
        """A firm_b user cannot see firm_a's engagement recent docs -- gets 404."""
        owner_a_headers = firm_a_owner["headers"]
        owner_b_headers = firm_b_owner["headers"]

        client_id_a = _setup_client(client, owner_a_headers)
        eng_id_a = _setup_engagement(client, owner_a_headers, client_id_a)

        r = client.get(f"/engagements/{eng_id_a}/recent-documents", headers=owner_b_headers)
        assert r.status_code == 404, (
            f"Firm B owner must not see firm A engagement; got {r.status_code}: {r.text}"
        )

    def test_view_in_eng_x_does_not_appear_in_eng_y(self, client, firm_a_owner):
        """A document viewed in engagement X must not appear in engagement Y's
        recent list, even if both engagements belong to the same firm and client."""
        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]

        client_id = _setup_client(client, headers)
        eng_x = _setup_engagement(client, headers, client_id, name="Eng X")
        eng_y = _setup_engagement(client, headers, client_id, name="Eng Y")

        doc_id = _upload_doc(client, headers, client_id, eng_x)

        # Record a view under engagement X.
        db = TestingSessionLocal()
        try:
            me = client.get("/users/me", headers=headers)
            user_id = uuid.UUID(me.json()["id"])
            from app.services.recent_documents_service import record_document_view
            record_document_view(
                db,
                firm_id=uuid.UUID(firm_id),
                user_id=user_id,
                engagement_id=uuid.UUID(eng_x),
                document_id=uuid.UUID(doc_id),
            )
        finally:
            db.close()

        # Recent list for engagement Y must not contain the document.
        r = client.get(f"/engagements/{eng_y}/recent-documents", headers=headers)
        assert r.status_code == 200, r.text
        ids = [item["document_id"] for item in r.json()]
        assert doc_id not in ids, (
            f"Document from eng_x must not appear in eng_y recent list; got {ids}"
        )


# ---------------------------------------------------------------------------
# f. None engagement_id guard -- firm_library documents are silently skipped
# ---------------------------------------------------------------------------

class TestNoneEngagementIdGuard:
    """Guard tests for the engagement_id=None early-return in record_document_view.

    Firm_library documents have no engagement (engagement_id=None).
    recent_document_views.engagement_id is NOT NULL. Without the guard, the
    INSERT raises an IntegrityError; without the rollback fix, that left the
    caller's session poisoned and caused a user-facing 500 on the very next
    query (the S3 presigned URL lookup).
    """

    def test_none_engagement_id_does_not_call_execute(self):
        """record_document_view with engagement_id=None must not call db.execute.

        Watched-fail procedure:
          1. Remove the 'if engagement_id is None: return' guard.
          2. Run this test -- db.execute.assert_not_called() fails because
             the insert is attempted.
          3. Restore the guard -- test passes.
        """
        from unittest.mock import MagicMock
        from app.services.recent_documents_service import record_document_view

        db = MagicMock()
        record_document_view(
            db,
            firm_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            engagement_id=None,
            document_id=uuid.uuid4(),
        )
        db.execute.assert_not_called()
        db.commit.assert_not_called()

    def test_none_engagement_id_returns_none(self):
        """record_document_view with engagement_id=None returns without raising."""
        from unittest.mock import MagicMock
        from app.services.recent_documents_service import record_document_view

        db = MagicMock()
        result = record_document_view(
            db,
            firm_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            engagement_id=None,
            document_id=uuid.uuid4(),
        )
        assert result is None

    def test_valid_engagement_id_still_creates_row(self, client, firm_a_owner):
        """record_document_view with a real engagement_id creates a row.

        Regression guard: confirms the None-check guard did not break the
        real, intended engagement-scoped behavior.

        Watched-fail procedure:
          1. Comment out db.execute(stmt) inside record_document_view.
          2. Run this test -- count is 0 instead of 1.
          3. Restore db.execute(stmt) -- count is 1.
        """
        from app.services.recent_documents_service import record_document_view

        firm_id = firm_a_owner["firm_id"]
        headers = firm_a_owner["headers"]

        client_id = _setup_client(client, headers)
        eng_id = _setup_engagement(client, headers, client_id)
        doc_id = _upload_doc(client, headers, client_id, eng_id)

        me = client.get("/users/me", headers=headers)
        user_id = uuid.UUID(me.json()["id"])

        db = TestingSessionLocal()
        try:
            record_document_view(
                db,
                firm_id=uuid.UUID(firm_id),
                user_id=user_id,
                engagement_id=uuid.UUID(eng_id),
                document_id=uuid.UUID(doc_id),
            )
        finally:
            db.close()

        assert _count_recent_rows(str(user_id), doc_id) == 1, (
            "Expected 1 recent_document_view row for a valid engagement-scoped call"
        )


# ---------------------------------------------------------------------------
# g. Rollback fix -- failed insert cannot poison the caller's session
# ---------------------------------------------------------------------------

class TestRollbackUnpoisonsSession:
    """Guard test for the db.rollback() call added to the except block.

    Without rollback, a failed INSERT leaves PostgreSQL in an aborted-
    transaction state; any subsequent query on the same session raises
    'current transaction is aborted', which is exactly what turned an
    ignorable recording failure into a user-facing 500 error.

    Construction: pass a non-existent firm_id UUID. The INSERT reaches the
    DB, hits a FK violation on firm_id, and PostgreSQL aborts the
    transaction. Without db.rollback(), the next SELECT raises
    InternalError/InFailedSqlTransaction. With it, the SELECT returns 1.

    This is a post-guard failure: engagement_id is non-None, so the guard
    passes and the insert is attempted; the FK violation is the failure path.
    """

    def test_rollback_allows_subsequent_query_after_failed_insert(self):
        """Failed record_document_view must not leave the session poisoned.

        Watched-fail procedure (confirms the test checks the real rollback):
          1. Remove db.rollback() from the except block in record_document_view.
          2. Run this test -- db.execute(text("SELECT 1")) raises
             sqlalchemy.exc.InternalError: current transaction is aborted.
          3. Restore db.rollback() -- SELECT returns 1 and the test passes.

        The failure is real and observable: PostgreSQL refuses to execute any
        statement after an aborted transaction until the session is rolled back.
        """
        from sqlalchemy import text
        from app.services.recent_documents_service import record_document_view

        db = TestingSessionLocal()
        try:
            record_document_view(
                db,
                firm_id=uuid.uuid4(),    # non-existent -- FK violation
                user_id=uuid.uuid4(),
                engagement_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
            )
            result = db.execute(text("SELECT 1")).scalar()
            assert result == 1, (
                f"Session must be usable after a failed record_document_view; "
                f"got {result!r} -- likely missing db.rollback() in except block"
            )
        finally:
            db.close()
