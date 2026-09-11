# tests/test_filesystem_phase6_task1.py
"""
Guard tests for Filesystem Phase 6 Task 1: direct upload paths for client and
firm_library scope.

Spec reference: Filesystem Build Specification, Sections 3 and 6.

Tests:
  1. firm_library upload-url + upload-complete: succeeds for manager, refused
     403 for plain staff -- watched-fail.
  2. client-scope upload-url + upload-complete: succeeds for manager, refused
     403 for plain staff -- watched-fail.
  3. Existing engagement-scoped path unaffected: plain member can still upload.
  4. Completed firm_library upload produces scope='firm_library', client_id None,
     engagement_id None -- confirmed via direct DB query.
  5. Completed client-scope upload produces scope='client', client_id set,
     engagement_id None -- confirmed via direct DB query.
  6. firm_library upload s3_key contains literal 'None' in client_id and
     engagement_id positions -- expected, accepted per Section 18 preserve list.
"""

import uuid
from unittest.mock import patch

import pytest

from tests.conftest import TestingSessionLocal
from app.models.document import Document
from app.models.engagement_member import EngagementMember
from app.models.user import User
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


def _add_member(firm_id, engagement_id, user_id):
    db = TestingSessionLocal()
    try:
        member = EngagementMember(
            firm_id=firm_id,
            engagement_id=engagement_id,
            user_id=user_id,
            is_administrator=False,
        )
        db.add(member)
        db.commit()
    finally:
        db.close()


def _login(test_client, email, password):
    r = test_client.post("/auth/token", json={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _get_doc_from_db(doc_id):
    db = TestingSessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc is None:
            return None
        return {
            "id": str(doc.id),
            "scope": doc.scope,
            "client_id": doc.client_id,
            "engagement_id": doc.engagement_id,
            "s3_key": doc.s3_key,
        }
    finally:
        db.close()


def _issue_url(test_client, headers, payload):
    with patch("app.services.s3._get_client") as mock_s3:
        mock_s3.return_value.generate_presigned_url.return_value = "https://s3.example/presigned"
        r = test_client.post("/documents/upload-url", json=payload, headers=headers)
    return r


def _complete_upload(test_client, headers, doc_id, payload):
    mock_meta = {"ContentLength": 512, "ContentType": "text/plain"}
    with patch("app.services.s3._get_client") as mock_s3:
        mock_s3.return_value.head_object.return_value = mock_meta
        r = test_client.post(f"/documents/{doc_id}/upload-complete", json=payload, headers=headers)
    return r


# ---------------------------------------------------------------------------
# 1. firm_library upload: manager succeeds, plain staff refused 403
# ---------------------------------------------------------------------------

class TestFirmLibraryUploadAuth:

    def test_firm_library_upload_url_refused_for_plain_staff(self, client, firm_a_owner):
        """Plain staff member gets 403 on upload-url with no client_id/engagement_id.

        Watched-fail: guard was temporarily removed to confirm this test goes red
        (200 instead of 403) before the fix was restored.
        """
        firm_id = firm_a_owner["firm_id"]

        email, password, _ = _create_user(firm_id, role=UserRole.staff)
        staff_headers = _login(client, email, password)

        r = _issue_url(client, staff_headers, {
            "filename": "template.pdf",
            "content_type": "application/pdf",
        })
        assert r.status_code == 403, (
            f"Plain staff must be refused 403 on firm_library upload-url; got {r.status_code}: {r.text}"
        )

    def test_firm_library_upload_url_allowed_for_manager(self, client, firm_a_owner):
        """Manager succeeds on upload-url with no client_id/engagement_id."""
        headers = firm_a_owner["headers"]

        r = _issue_url(client, headers, {
            "filename": "template.pdf",
            "content_type": "application/pdf",
        })
        assert r.status_code == 200, (
            f"Manager must succeed on firm_library upload-url; got {r.status_code}: {r.text}"
        )
        assert "document_id" in r.json()
        assert "upload_url" in r.json()

    def test_firm_library_complete_upload_refused_for_plain_staff(self, client, firm_a_owner):
        """Plain staff member gets 403 on upload-complete with no client_id/engagement_id."""
        firm_id = firm_a_owner["firm_id"]
        owner_headers = firm_a_owner["headers"]

        # Issue the URL as manager to get a valid doc_id.
        url_r = _issue_url(client, owner_headers, {
            "filename": "template.pdf",
            "content_type": "application/pdf",
        })
        assert url_r.status_code == 200, url_r.text
        doc_id = url_r.json()["document_id"]

        email, password, _ = _create_user(firm_id, role=UserRole.staff)
        staff_headers = _login(client, email, password)

        r = _complete_upload(client, staff_headers, doc_id, {
            "filename": "template.pdf",
            "content_type": "application/pdf",
        })
        assert r.status_code == 403, (
            f"Plain staff must be refused 403 on firm_library complete_upload; got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# 2. client-scope upload: manager succeeds, plain staff refused 403
# ---------------------------------------------------------------------------

class TestClientScopeUploadAuth:

    def test_client_scope_upload_url_refused_for_plain_staff(self, client, firm_a_owner):
        """Plain staff member gets 403 on upload-url with client_id but no engagement_id.

        Watched-fail: guard was temporarily removed to confirm this test goes red
        (200 instead of 403) before the fix was restored.
        """
        firm_id = firm_a_owner["firm_id"]
        owner_headers = firm_a_owner["headers"]

        cl = client.post("/clients/", json={"name": f"Client-{uuid.uuid4()}"}, headers=owner_headers)
        assert cl.status_code == 201
        client_id = cl.json()["id"]

        email, password, _ = _create_user(firm_id, role=UserRole.staff)
        staff_headers = _login(client, email, password)

        r = _issue_url(client, staff_headers, {
            "client_id": client_id,
            "filename": "formation.pdf",
            "content_type": "application/pdf",
        })
        assert r.status_code == 403, (
            f"Plain staff must be refused 403 on client-scope upload-url; got {r.status_code}: {r.text}"
        )

    def test_client_scope_upload_url_allowed_for_manager(self, client, firm_a_owner):
        """Manager succeeds on upload-url with client_id but no engagement_id."""
        owner_headers = firm_a_owner["headers"]

        cl = client.post("/clients/", json={"name": f"Client-{uuid.uuid4()}"}, headers=owner_headers)
        assert cl.status_code == 201
        client_id = cl.json()["id"]

        r = _issue_url(client, owner_headers, {
            "client_id": client_id,
            "filename": "formation.pdf",
            "content_type": "application/pdf",
        })
        assert r.status_code == 200, (
            f"Manager must succeed on client-scope upload-url; got {r.status_code}: {r.text}"
        )
        assert "document_id" in r.json()

    def test_client_scope_complete_upload_refused_for_plain_staff(self, client, firm_a_owner):
        """Plain staff member gets 403 on upload-complete with client_id but no engagement_id."""
        firm_id = firm_a_owner["firm_id"]
        owner_headers = firm_a_owner["headers"]

        cl = client.post("/clients/", json={"name": f"Client-{uuid.uuid4()}"}, headers=owner_headers)
        assert cl.status_code == 201
        client_id = cl.json()["id"]

        url_r = _issue_url(client, owner_headers, {
            "client_id": client_id,
            "filename": "formation.pdf",
            "content_type": "application/pdf",
        })
        assert url_r.status_code == 200, url_r.text
        doc_id = url_r.json()["document_id"]

        email, password, _ = _create_user(firm_id, role=UserRole.staff)
        staff_headers = _login(client, email, password)

        r = _complete_upload(client, staff_headers, doc_id, {
            "client_id": client_id,
            "filename": "formation.pdf",
            "content_type": "application/pdf",
        })
        assert r.status_code == 403, (
            f"Plain staff must be refused 403 on client-scope complete_upload; got {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# 3. Existing engagement-scoped path: plain member can still upload
# ---------------------------------------------------------------------------

class TestEngagementScopeUnaffected:

    def test_engagement_member_can_still_upload_via_direct_path(self, client, firm_a_owner):
        """Plain engagement member continues to succeed on the existing engagement-scoped
        upload path. Confirms Step 5: the engagement path is completely unaffected."""
        firm_id = firm_a_owner["firm_id"]
        owner_headers = firm_a_owner["headers"]

        cl = client.post("/clients/", json={"name": f"Client-{uuid.uuid4()}"}, headers=owner_headers)
        assert cl.status_code == 201
        client_id = cl.json()["id"]
        eng = client.post(
            "/engagements/",
            json={"name": f"Eng-{uuid.uuid4()}", "client_id": client_id},
            headers=owner_headers,
        )
        assert eng.status_code == 201
        eng_id = eng.json()["id"]

        email, password, user_id = _create_user(firm_id, role=UserRole.staff)
        _add_member(firm_id, eng_id, user_id)
        staff_headers = _login(client, email, password)

        url_r = _issue_url(client, staff_headers, {
            "client_id": client_id,
            "engagement_id": eng_id,
            "filename": "filing.pdf",
            "content_type": "application/pdf",
        })
        assert url_r.status_code == 200, (
            f"Engagement member must still succeed on engagement-scoped upload-url; got {url_r.status_code}: {url_r.text}"
        )

        doc_id = url_r.json()["document_id"]
        complete_r = _complete_upload(client, staff_headers, doc_id, {
            "client_id": client_id,
            "engagement_id": eng_id,
            "filename": "filing.pdf",
            "content_type": "application/pdf",
        })
        assert complete_r.status_code == 200, (
            f"Engagement member must succeed on engagement-scoped complete_upload; got {complete_r.status_code}: {complete_r.text}"
        )

        row = _get_doc_from_db(doc_id)
        assert row["scope"] == "engagement"
        assert str(row["engagement_id"]) == eng_id
        assert str(row["client_id"]) == client_id


# ---------------------------------------------------------------------------
# 4. firm_library upload produces correct scope and null IDs in DB
# ---------------------------------------------------------------------------

class TestFirmLibraryDocumentRow:

    def test_firm_library_upload_creates_correct_document_row(self, client, firm_a_owner):
        """Completed firm_library upload produces scope='firm_library', client_id None,
        engagement_id None -- confirmed via direct DB query, not just response status."""
        owner_headers = firm_a_owner["headers"]

        url_r = _issue_url(client, owner_headers, {
            "filename": "firm_template.pdf",
            "content_type": "application/pdf",
        })
        assert url_r.status_code == 200, url_r.text
        doc_id = url_r.json()["document_id"]

        complete_r = _complete_upload(client, owner_headers, doc_id, {
            "filename": "firm_template.pdf",
            "content_type": "application/pdf",
        })
        assert complete_r.status_code == 200, complete_r.text

        row = _get_doc_from_db(doc_id)
        assert row is not None
        assert row["scope"] == "firm_library", f"Expected scope='firm_library'; got '{row['scope']}'"
        assert row["client_id"] is None, f"Expected client_id=None; got {row['client_id']}"
        assert row["engagement_id"] is None, f"Expected engagement_id=None; got {row['engagement_id']}"


# ---------------------------------------------------------------------------
# 5. client-scope upload produces correct scope and IDs in DB
# ---------------------------------------------------------------------------

class TestClientScopeDocumentRow:

    def test_client_scope_upload_creates_correct_document_row(self, client, firm_a_owner):
        """Completed client-scope upload produces scope='client', client_id set,
        engagement_id None -- confirmed via direct DB query."""
        owner_headers = firm_a_owner["headers"]

        cl = client.post("/clients/", json={"name": f"Client-{uuid.uuid4()}"}, headers=owner_headers)
        assert cl.status_code == 201
        client_id = cl.json()["id"]

        url_r = _issue_url(client, owner_headers, {
            "client_id": client_id,
            "filename": "formation_doc.pdf",
            "content_type": "application/pdf",
        })
        assert url_r.status_code == 200, url_r.text
        doc_id = url_r.json()["document_id"]

        complete_r = _complete_upload(client, owner_headers, doc_id, {
            "client_id": client_id,
            "filename": "formation_doc.pdf",
            "content_type": "application/pdf",
        })
        assert complete_r.status_code == 200, complete_r.text

        row = _get_doc_from_db(doc_id)
        assert row is not None
        assert row["scope"] == "client", f"Expected scope='client'; got '{row['scope']}'"
        assert str(row["client_id"]) == client_id, f"Expected client_id={client_id}; got {row['client_id']}"
        assert row["engagement_id"] is None, f"Expected engagement_id=None; got {row['engagement_id']}"


# ---------------------------------------------------------------------------
# 6. firm_library s3_key contains literal 'None' -- expected, accepted behavior
# ---------------------------------------------------------------------------

class TestFirmLibraryS3Key:

    def test_firm_library_s3_key_contains_none_segments(self, client, firm_a_owner):
        """The s3_key for a firm_library upload contains the literal string 'None' in
        the client_id and engagement_id positions.

        This is expected, accepted behavior per the Section 18 preserve list:
        _build_s3_key is not changed, and this key shape already exists in production
        for firm_library copies (copy_document uses the same function). A future task
        may migrate to a cleaner key scheme, but this is explicitly out of scope here.
        Do NOT treat this as a bug or attempt to fix it in this task.
        """
        owner_headers = firm_a_owner["headers"]

        url_r = _issue_url(client, owner_headers, {
            "filename": "template_for_key_check.pdf",
            "content_type": "application/pdf",
        })
        assert url_r.status_code == 200, url_r.text
        doc_id = url_r.json()["document_id"]
        s3_key_from_url = url_r.json()["s3_key"]

        # The key should contain 'None' where client_id and engagement_id would be.
        assert "None" in s3_key_from_url, (
            f"Expected 'None' in firm_library s3_key (accepted behavior per Section 18); got {s3_key_from_url}"
        )

        complete_r = _complete_upload(client, owner_headers, doc_id, {
            "filename": "template_for_key_check.pdf",
            "content_type": "application/pdf",
        })
        assert complete_r.status_code == 200, complete_r.text

        row = _get_doc_from_db(doc_id)
        assert row is not None
        assert "None" in row["s3_key"], (
            f"Expected 'None' in stored s3_key (accepted behavior per Section 18); got {row['s3_key']}"
        )


# ---------------------------------------------------------------------------
# description field threading
# ---------------------------------------------------------------------------

class TestDescriptionField:

    def test_description_persists_on_firm_library_upload(self, client, firm_a_owner):
        """A firm_library-scope complete_upload with description set persists the
        value and returns it in DocumentOut. Confirms description threads through
        UploadCompleteRequest -> complete_upload service -> create_document -> DB.
        """
        owner_headers = firm_a_owner["headers"]

        url_r = _issue_url(client, owner_headers, {
            "filename": "engagement_letter.pdf",
            "content_type": "application/pdf",
            "description": "Standard engagement letter for individual returns",
        })
        assert url_r.status_code == 200, url_r.text
        doc_id = url_r.json()["document_id"]

        complete_r = _complete_upload(client, owner_headers, doc_id, {
            "filename": "engagement_letter.pdf",
            "content_type": "application/pdf",
            "description": "Standard engagement letter for individual returns",
        })
        assert complete_r.status_code == 200, complete_r.text

        body = complete_r.json()
        doc_resp = body.get("document")
        assert doc_resp is not None, "Expected document in response"
        assert doc_resp["description"] == "Standard engagement letter for individual returns", (
            f"description must be returned in DocumentOut; got {doc_resp.get('description')}"
        )

        row = _get_doc_from_db(doc_id)
        assert row is not None
        assert row["scope"] == "firm_library"

        # Also confirm the value is in the DB row directly.
        from tests.conftest import TestingSessionLocal
        from app.models.document import Document
        db = TestingSessionLocal()
        try:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            assert doc is not None
            assert doc.description == "Standard engagement letter for individual returns", (
                f"description must persist in DB; got {doc.description}"
            )
        finally:
            db.close()

    def test_description_null_when_omitted(self, client, firm_a_owner):
        """A complete_upload with no description set returns description: null,
        not an error.
        """
        owner_headers = firm_a_owner["headers"]

        url_r = _issue_url(client, owner_headers, {
            "filename": "no_desc.pdf",
            "content_type": "application/pdf",
        })
        assert url_r.status_code == 200, url_r.text
        doc_id = url_r.json()["document_id"]

        complete_r = _complete_upload(client, owner_headers, doc_id, {
            "filename": "no_desc.pdf",
            "content_type": "application/pdf",
        })
        assert complete_r.status_code == 200, complete_r.text

        doc_resp = complete_r.json().get("document")
        assert doc_resp is not None
        assert doc_resp["description"] is None, (
            f"description must be null when not supplied; got {doc_resp.get('description')}"
        )
