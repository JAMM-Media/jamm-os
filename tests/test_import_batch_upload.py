# tests/test_import_batch_upload.py
"""
Guard tests for import batch Phase 3 -- staging upload URLs and upload-complete.

Tests:
  (a) A user who was an engagement administrator at confirmation but has since
      had is_administrator revoked is refused 422 on upload-url, proving the
      re-authorization runs per-call rather than being cached.
      Watched red by temporarily skipping the assert_can_bulk_import re-check.
  (b) Calling upload-url or upload-complete on an item in a draft batch is
      refused 422 (batch must be confirmed).
  (c) Calling upload-complete before upload-url (no staging_s3_key) is refused 422.
  (d) A mocked oversized HEAD response causes the item to be marked failed with
      FILE_TOO_LARGE and returns 413.
      Watched red by temporarily removing the size check.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from app.core.enums import UserRole
from app.core.security import get_password_hash
from app.models.engagement_member import EngagementMember
from app.models.import_batch import ImportBatch
from app.models.import_item import ImportItem
from app.models.user import User
from app.services.import_batch_service import ERROR_FILE_TOO_LARGE, MAX_DIRECT_UPLOAD_BYTES
from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_user(firm_id: str, role: UserRole = UserRole.staff):
    email = f"user-{uuid.uuid4()}@test.com"
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=uuid.UUID(firm_id),
            email=email,
            hashed_password=get_password_hash("testpass"),
            full_name="Test",
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return email, str(user.id)
    finally:
        db.close()


def _login(test_client, email: str) -> dict:
    r = test_client.post("/auth/token", json={"username": email, "password": "testpass"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _set_member_admin(firm_id: str, engagement_id: str, user_id: str, is_administrator: bool):
    db = TestingSessionLocal()
    try:
        member = db.query(EngagementMember).filter(
            EngagementMember.firm_id == uuid.UUID(firm_id),
            EngagementMember.engagement_id == uuid.UUID(engagement_id),
            EngagementMember.user_id == uuid.UUID(user_id),
        ).first()
        if member:
            member.is_administrator = is_administrator
        else:
            db.add(EngagementMember(
                firm_id=uuid.UUID(firm_id),
                engagement_id=uuid.UUID(engagement_id),
                user_id=uuid.UUID(user_id),
                is_administrator=is_administrator,
            ))
        db.commit()
    finally:
        db.close()


def _setup_confirmed_batch(test_client, firm_a_owner) -> tuple[str, str, str, str]:
    """Return (firm_id, eng_id, batch_id, item_id) with batch already confirmed."""
    headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]

    r = test_client.post("/clients/", json={"name": f"UL Client {uuid.uuid4()}"}, headers=headers)
    assert r.status_code == 201, r.text
    client_id = r.json()["id"]

    r = test_client.post(
        "/engagements/", json={"name": "UL Eng", "client_id": client_id}, headers=headers
    )
    assert r.status_code == 201, r.text
    eng_id = r.json()["id"]

    payload = {
        "scope": "engagement",
        "client_id": client_id,
        "engagement_id": eng_id,
        "conflict_policy": "skip",
        "items": [{"relative_path": "folder/file.pdf", "filename": "file.pdf", "expected_bytes": 1024}],
    }
    r = test_client.post("/import-batches/", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    batch_id = r.json()["id"]
    item_id = r.json()["items"][0]["id"]

    r = test_client.post(f"/import-batches/{batch_id}/confirm", headers=headers)
    assert r.status_code == 200, r.text

    return firm_id, eng_id, batch_id, item_id


# ---------------------------------------------------------------------------
# Test (a): revoked administrator is refused on upload-url
# ---------------------------------------------------------------------------

def test_revoked_administrator_refused_on_upload_url(client, firm_a_owner):
    firm_id, eng_id, batch_id, item_id = _setup_confirmed_batch(client, firm_a_owner)

    email, user_id = _create_user(firm_id, UserRole.staff)
    _set_member_admin(firm_id, eng_id, user_id, is_administrator=True)
    headers = _login(client, email)

    with patch("app.services.s3.generate_presigned_put_url", return_value="https://s3.example.com/fake"):
        r = client.post(
            f"/import-batches/{batch_id}/items/{item_id}/upload-url", headers=headers
        )
    assert r.status_code == 200, f"Expected 200 while admin, got {r.status_code}: {r.text}"

    # Revoke is_administrator
    _set_member_admin(firm_id, eng_id, user_id, is_administrator=False)

    r = client.post(f"/import-batches/{batch_id}/items/{item_id}/upload-url", headers=headers)
    assert r.status_code == 422, f"Expected 422 after revocation, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# Test (b): upload-url and upload-complete on a draft batch are refused 422
# ---------------------------------------------------------------------------

def test_upload_url_on_draft_batch_refused(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]

    r = test_client_post = client.post("/clients/", json={"name": "Draft UL"}, headers=headers)
    client_id = r.json()["id"]
    r = client.post("/engagements/", json={"name": "Draft Eng", "client_id": client_id}, headers=headers)
    eng_id = r.json()["id"]

    payload = {
        "scope": "engagement",
        "client_id": client_id,
        "engagement_id": eng_id,
        "conflict_policy": "skip",
        "items": [{"relative_path": "file.pdf", "filename": "file.pdf", "expected_bytes": 512}],
    }
    r = client.post("/import-batches/", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    batch_id = r.json()["id"]
    item_id = r.json()["items"][0]["id"]
    # Batch is still in draft -- do NOT confirm

    r = client.post(f"/import-batches/{batch_id}/items/{item_id}/upload-url", headers=headers)
    assert r.status_code == 422, f"Expected 422 for draft batch, got {r.status_code}: {r.text}"
    assert "confirmed" in r.json()["detail"].lower()

    r = client.post(f"/import-batches/{batch_id}/items/{item_id}/upload-complete", headers=headers)
    assert r.status_code == 422, f"Expected 422 for draft batch, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# Test (c): upload-complete without prior upload-url is refused 422
# ---------------------------------------------------------------------------

def test_upload_complete_without_prior_upload_url_refused(client, firm_a_owner):
    _, _, batch_id, item_id = _setup_confirmed_batch(client, firm_a_owner)
    headers = firm_a_owner["headers"]

    # No upload-url call -- item has no staging_s3_key yet
    r = client.post(f"/import-batches/{batch_id}/items/{item_id}/upload-complete", headers=headers)
    assert r.status_code == 422, f"Expected 422 for missing staging_s3_key, got {r.status_code}: {r.text}"
    assert "upload-url" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test (d): oversized staged file causes FILE_TOO_LARGE and 413
# ---------------------------------------------------------------------------

def test_oversized_file_is_marked_failed_with_file_too_large(client, firm_a_owner):
    _, _, batch_id, item_id = _setup_confirmed_batch(client, firm_a_owner)
    headers = firm_a_owner["headers"]

    # Issue upload URL first (mocking S3)
    with patch("app.services.s3.generate_presigned_put_url", return_value="https://s3.example.com/fake"):
        r = client.post(
            f"/import-batches/{batch_id}/items/{item_id}/upload-url", headers=headers
        )
    assert r.status_code == 200, r.text

    # Mock HEAD returning a size larger than MAX_DIRECT_UPLOAD_BYTES
    oversized = MAX_DIRECT_UPLOAD_BYTES + 1
    fake_head = MagicMock(return_value={"ContentLength": oversized})

    with patch("app.services.s3.head_object", fake_head):
        with patch("app.services.s3.delete_object"):
            r = client.post(
                f"/import-batches/{batch_id}/items/{item_id}/upload-complete", headers=headers
            )
    assert r.status_code == 413, f"Expected 413, got {r.status_code}: {r.text}"

    # Verify item is marked failed with the right error_code in DB
    db = TestingSessionLocal()
    try:
        item = db.query(ImportItem).filter(ImportItem.id == uuid.UUID(item_id)).first()
        assert item.status == "failed"
        assert item.error_code == ERROR_FILE_TOO_LARGE
        assert item.attempt_count == 1
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Ordering test: permission error must precede status error
# ---------------------------------------------------------------------------

def test_unauthorized_user_gets_permission_error_not_status_error(client, firm_a_owner):
    """
    A plain staff member (no trio row) calling upload-url on a batch that is
    still in draft status must receive the 422 for lack of permission, not the
    422 for wrong batch status. The auth check must run before status validation.

    Before the ordering fix: batch status is validated inside
    _get_confirmed_batch_and_planned_item BEFORE assert_can_bulk_import runs,
    so the caller learns batch status without ever being auth-checked.
    After the fix: batch existence is checked, auth runs, THEN status is checked.
    """
    headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]

    r = client.post("/clients/", json={"name": f"Order Test {uuid.uuid4()}"}, headers=headers)
    client_id = r.json()["id"]
    r = client.post("/engagements/", json={"name": "Order Eng", "client_id": client_id}, headers=headers)
    eng_id = r.json()["id"]

    payload = {
        "scope": "engagement",
        "client_id": client_id,
        "engagement_id": eng_id,
        "conflict_policy": "skip",
        "items": [{"relative_path": "file.pdf", "filename": "file.pdf", "expected_bytes": 512}],
    }
    r = client.post("/import-batches/", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    batch_id = r.json()["id"]
    item_id = r.json()["items"][0]["id"]
    # Batch deliberately left in draft -- NOT confirmed

    # Create a plain staff user with no engagement membership at all
    email, _ = _create_user(firm_id, UserRole.staff)
    noauth_headers = _login(client, email)

    r = client.post(
        f"/import-batches/{batch_id}/items/{item_id}/upload-url",
        headers=noauth_headers,
    )
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"
    detail = r.json()["detail"]
    # The error must be the permission error, not the status error
    assert "administrator" in detail.lower() or "permission" in detail.lower() or "import" in detail.lower(), (
        f"Expected permission error, got: {detail!r}"
    )
    assert "draft" not in detail.lower() and "confirmed" not in detail.lower(), (
        f"Got batch-status error instead of permission error: {detail!r}"
    )
