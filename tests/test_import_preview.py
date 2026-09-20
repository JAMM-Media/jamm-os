# tests/test_import_preview.py
"""
Guard tests for GET /import-batches/{batch_id}/preview (Phase 4 read path).

Tests:
  (a) Calling preview on a batch whose item path includes a folder that does
      not yet exist produces resolved: False for that item, and no folder row
      is created in the database as a side effect.
      Watched red by temporarily substituting the side-effecting
      _resolve_destination_folder for the read-only version inside preview_batch,
      confirming a folder is wrongly created just from calling preview, then
      restoring and confirming no folder is created.
  (b) An item whose destination path fully resolves and collides with a live
      document returns has_conflict: True with the correct existing_document_id
      and existing_document_filename.
  (c) An item with no collision returns has_conflict: False.
  (d) Auth-before-status ordering: an unauthorized plain staff member calling
      preview on a batch that is in a non-previewable status receives the
      permission refusal, not the status error. The caller must not learn batch
      state before being auth-checked.
      Watched red by temporarily monkeypatching preview_batch to check status
      before auth, confirming the wrong error surfaces, then restoring.
"""

import uuid
from unittest.mock import patch

import pytest

from app.core.enums import UserRole
from app.core.security import get_password_hash
from app.models.document import Document
from app.models.document_folder import DocumentFolder
from app.models.engagement_member import EngagementMember
from app.models.import_batch import ImportBatch
from app.models.user import User
from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_user(firm_id: str, role: UserRole = UserRole.firm_owner):
    email = f"prev-{uuid.uuid4().hex[:8]}@test.com"
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=uuid.UUID(firm_id),
            email=email,
            hashed_password=get_password_hash("testpass"),
            full_name="Preview Test",
            role=role,
        )
        db.add(user)
        db.commit()
        return email, str(user.id)
    finally:
        db.close()


def _login(test_client, email: str) -> dict:
    r = test_client.post("/auth/token", json={"username": email, "password": "testpass"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _add_member(firm_id: str, eng_id: str, user_id: str, *, is_administrator: bool):
    db = TestingSessionLocal()
    try:
        db.add(EngagementMember(
            firm_id=uuid.UUID(firm_id),
            engagement_id=uuid.UUID(eng_id),
            user_id=uuid.UUID(user_id),
            is_administrator=is_administrator,
        ))
        db.commit()
    finally:
        db.close()


def _setup(client, firm_a_owner) -> tuple[str, str, str, dict]:
    """Return (firm_id, client_id, eng_id, headers)."""
    headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]

    r = client.post("/clients/", json={"name": f"Prev-{uuid.uuid4().hex[:6]}"}, headers=headers)
    assert r.status_code == 201, r.text
    client_id = r.json()["id"]

    r = client.post("/engagements/", json={"name": f"Prev-Eng-{uuid.uuid4().hex[:6]}", "client_id": client_id}, headers=headers)
    assert r.status_code == 201, r.text
    eng_id = r.json()["id"]

    return firm_id, client_id, eng_id, headers


def _create_batch(client, headers, client_id, eng_id, items=None):
    """Create a draft batch and return the full response JSON."""
    if items is None:
        items = [{"relative_path": "file.pdf", "filename": "file.pdf", "expected_bytes": 512}]
    payload = {
        "scope": "engagement",
        "client_id": client_id,
        "engagement_id": eng_id,
        "conflict_policy": "skip",
        "items": items,
    }
    r = client.post("/import-batches/", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _count_folders(firm_id: str) -> int:
    db = TestingSessionLocal()
    try:
        return db.query(DocumentFolder).filter(
            DocumentFolder.firm_id == uuid.UUID(firm_id),
        ).count()
    finally:
        db.close()


def _insert_document(firm_id: str, client_id: str, eng_id: str, filename: str, folder_id=None) -> str:
    """Insert a live Document row directly and return its id as a string."""
    db = TestingSessionLocal()
    try:
        doc = Document(
            firm_id=uuid.UUID(firm_id),
            client_id=uuid.UUID(client_id),
            engagement_id=uuid.UUID(eng_id),
            scope="engagement",
            filename=filename,
            s3_key=f"{firm_id}/{client_id}/{eng_id}/{uuid.uuid4()}/{filename}",
            content_type="application/pdf",
            size_bytes=512,
            folder_id=uuid.UUID(folder_id) if folder_id else None,
        )
        db.add(doc)
        db.commit()
        return str(doc.id)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test (a): unresolved path produces resolved: False, no folder side effect
# ---------------------------------------------------------------------------

def test_preview_unresolved_path_returns_false_and_creates_no_folder(client, firm_a_owner):
    """
    An item whose relative_path includes a subdirectory that does not yet exist
    must produce resolved: False. Calling preview must not create that folder
    as a side effect.

    RED phase: temporarily swap in _resolve_destination_folder (side-effecting)
    to confirm a folder IS wrongly created just from calling preview.
    After restore: confirm no folder is created and resolved is False.
    """
    firm_id, client_id, eng_id, headers = _setup(client, firm_a_owner)

    batch = _create_batch(
        client, headers, client_id, eng_id,
        items=[{
            "relative_path": "MissingFolder/report.pdf",
            "filename": "report.pdf",
            "expected_bytes": 512,
        }],
    )
    batch_id = batch["id"]

    folders_before = _count_folders(firm_id)

    # --- RED phase: temporarily use the side-effecting resolver ---
    import app.services.import_finalization_service as fin_svc
    from app.services.import_finalization_service import _resolve_destination_folder

    def _side_effecting_wrapper(db, batch_obj, path):
        # Calls the real create-folder-if-missing version and claims full resolution.
        folder_id = _resolve_destination_folder(db, batch_obj, path)
        return folder_id, True

    original_readonly = fin_svc._resolve_destination_folder_readonly
    fin_svc._resolve_destination_folder_readonly = _side_effecting_wrapper
    try:
        r = client.get(f"/import-batches/{batch_id}/preview", headers=headers)
        assert r.status_code == 200, r.text
        items_out = r.json()["items"]
        # With the broken version the folder was created, so resolved=True
        assert items_out[0]["resolved"] is True, (
            f"RED: expected resolved=True from side-effecting resolver, got {items_out[0]['resolved']}"
        )
        folders_after_red = _count_folders(firm_id)
        assert folders_after_red > folders_before, (
            f"RED: expected a folder to be created as a side effect of preview; "
            f"folder count before={folders_before}, after={folders_after_red}"
        )
        # Watched-fail message if the above assert fails:
        # AssertionError: RED: expected a folder to be created ... folder count before=0, after=0
    finally:
        fin_svc._resolve_destination_folder_readonly = original_readonly

    # --- GREEN phase: delete the folder wrongly created by the red phase, then re-run ---
    # The folder was created as a side effect of the broken red-phase preview call.
    # Delete it so the green phase starts from a clean state where no subfolder exists.
    db = TestingSessionLocal()
    try:
        for f in db.query(DocumentFolder).filter(
            DocumentFolder.firm_id == uuid.UUID(firm_id),
        ).all():
            db.delete(f)
        db.commit()
    finally:
        db.close()

    folders_before_green = _count_folders(firm_id)
    assert folders_before_green == 0, (
        f"Setup error: expected 0 folders before green phase, got {folders_before_green}"
    )

    r = client.get(f"/import-batches/{batch_id}/preview", headers=headers)
    assert r.status_code == 200, r.text
    items_out = r.json()["items"]

    item = items_out[0]
    assert item["resolved"] is False, (
        f"Expected resolved=False when subfolder does not exist, got {item['resolved']}"
    )
    assert item["has_conflict"] is False

    folders_after_green = _count_folders(firm_id)
    assert folders_after_green == folders_before_green, (
        f"Preview must not create any folders: count before={folders_before_green}, "
        f"after={folders_after_green}"
    )


# ---------------------------------------------------------------------------
# Test (b): resolved path with collision returns has_conflict: True
# ---------------------------------------------------------------------------

def test_preview_collision_returns_has_conflict_true_with_document_details(client, firm_a_owner):
    """
    An item whose destination path fully resolves and whose filename matches
    a live document at that location must return has_conflict: True with the
    correct existing_document_id and existing_document_filename.
    """
    firm_id, client_id, eng_id, headers = _setup(client, firm_a_owner)

    # Pre-seed a live document at root (no folder) with the same filename.
    existing_doc_id = _insert_document(firm_id, client_id, eng_id, "report.pdf")

    # Item sits at destination root: no subdirectory, just the filename.
    batch = _create_batch(
        client, headers, client_id, eng_id,
        items=[{
            "relative_path": "report.pdf",
            "filename": "report.pdf",
            "expected_bytes": 512,
        }],
    )
    batch_id = batch["id"]

    r = client.get(f"/import-batches/{batch_id}/preview", headers=headers)
    assert r.status_code == 200, r.text
    items_out = r.json()["items"]

    item = items_out[0]
    assert item["resolved"] is True, f"Expected resolved=True for root-level item; got {item['resolved']}"
    assert item["has_conflict"] is True, f"Expected has_conflict=True; got {item['has_conflict']}"
    assert item["existing_document_id"] == existing_doc_id, (
        f"Expected existing_document_id={existing_doc_id!r}, got {item['existing_document_id']!r}"
    )
    assert item["existing_document_filename"] == "report.pdf", (
        f"Expected existing_document_filename='report.pdf', got {item['existing_document_filename']!r}"
    )


# ---------------------------------------------------------------------------
# Test (c): resolved path with no collision returns has_conflict: False
# ---------------------------------------------------------------------------

def test_preview_no_collision_returns_has_conflict_false(client, firm_a_owner):
    """
    An item whose destination path fully resolves and whose filename does not
    match any live document must return has_conflict: False.
    """
    firm_id, client_id, eng_id, headers = _setup(client, firm_a_owner)

    # No pre-existing document.
    batch = _create_batch(
        client, headers, client_id, eng_id,
        items=[{
            "relative_path": "unique-file.pdf",
            "filename": "unique-file.pdf",
            "expected_bytes": 512,
        }],
    )
    batch_id = batch["id"]

    r = client.get(f"/import-batches/{batch_id}/preview", headers=headers)
    assert r.status_code == 200, r.text
    items_out = r.json()["items"]

    item = items_out[0]
    assert item["resolved"] is True
    assert item["has_conflict"] is False, f"Expected has_conflict=False; got {item['has_conflict']}"
    assert item["existing_document_id"] is None
    assert item["existing_document_filename"] is None


# ---------------------------------------------------------------------------
# Test (d): auth check runs before status check
# ---------------------------------------------------------------------------

def test_preview_auth_check_runs_before_status_check(client, firm_a_owner):
    """
    A plain staff member with no trio row calling preview on a batch in a
    non-previewable status must receive the permission error, not the status
    error. The caller must not learn batch state before being auth-checked.

    RED phase: temporarily monkeypatch preview_batch to check status before
    auth, confirming the wrong (status) error surfaces first.
    After restore: confirm the permission error fires first.
    """
    firm_id, client_id, eng_id, headers = _setup(client, firm_a_owner)

    batch = _create_batch(client, headers, client_id, eng_id)
    batch_id = batch["id"]

    # Force the batch into a non-previewable terminal status directly in the DB.
    db = TestingSessionLocal()
    try:
        b = db.query(ImportBatch).filter(ImportBatch.id == uuid.UUID(batch_id)).first()
        b.status = "completed_with_errors"
        db.commit()
    finally:
        db.close()

    # Create a plain staff user with no engagement membership.
    noauth_email, noauth_uid = _create_user(firm_id, UserRole.staff)
    noauth_headers = _login(client, noauth_email)

    # --- RED phase: temporarily swap preview_batch to check status before auth ---
    import app.services.import_batch_service as batch_svc
    from fastapi import HTTPException
    from app.services.document_access import assert_can_bulk_import

    def _wrong_order_preview(*, db, firm_id, batch_id, user):
        # Status check before auth -- exposes batch state to unauthorized caller.
        batch_obj = batch_svc._get_batch_for_firm(db, firm_id, batch_id)
        if batch_obj.status not in ("draft", "confirmed"):
            raise HTTPException(
                status_code=422,
                detail=f"Preview is only available for batches in draft or confirmed status; current status is '{batch_obj.status}'",
            )
        assert_can_bulk_import(
            db=db, user=user, scope=batch_obj.scope,
            engagement_id=batch_obj.engagement_id, firm_id=firm_id,
        )
        return []

    original_preview = batch_svc.preview_batch
    batch_svc.preview_batch = _wrong_order_preview
    try:
        r = client.get(f"/import-batches/{batch_id}/preview", headers=noauth_headers)
        assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"
        detail = r.json()["detail"]
        # With wrong ordering the status error fires: caller learns the batch is completed_with_errors
        assert "completed_with_errors" in detail or "draft or confirmed" in detail, (
            f"RED: expected status error to surface first, got: {detail!r}"
        )
        assert "administrator" not in detail.lower(), (
            f"RED: permission error should not have fired yet, got: {detail!r}"
        )
        # Watched-fail: if this assert_in passes, the status error IS leaking to the unauthorized caller.
    finally:
        batch_svc.preview_batch = original_preview

    # --- GREEN phase: real ordering -- permission error fires first ---
    r = client.get(f"/import-batches/{batch_id}/preview", headers=noauth_headers)
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"
    detail = r.json()["detail"]

    assert "administrator" in detail.lower() or "manager" in detail.lower(), (
        f"Expected permission error, got: {detail!r}"
    )
    assert "draft" not in detail.lower() and "confirmed" not in detail.lower(), (
        f"Got status error instead of permission error: {detail!r}"
    )
    assert "completed_with_errors" not in detail, (
        f"Batch status leaked to unauthorized caller: {detail!r}"
    )
