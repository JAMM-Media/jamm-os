# tests/test_import_batch_patch.py
"""
Guard tests for PATCH /import-batches/{batch_id} (conflict_policy update).

Tests:
  (a) A draft batch's conflict_policy can be successfully changed via PATCH,
      and a subsequent GET reflects the new value.
  (b) Attempting to PATCH a batch that has already been confirmed is refused 422,
      and the conflict_policy is unchanged in the database afterward.
      Watched red by temporarily removing the status check, confirming a confirmed
      batch's policy wrongly changes, then restoring.
  (c) Auth-before-status ordering: an unauthorized caller (plain staff, no trio
      membership) attempting to PATCH a batch in a non-draft status receives the
      permission refusal, not a status error, and does not learn the batch's status.
      Watched red by temporarily reordering the checks, confirming the wrong error
      surfaces, then restoring.
"""

import uuid

import pytest
from fastapi import HTTPException

from app.core.enums import UserRole
from app.core.security import get_password_hash
from app.models.engagement_member import EngagementMember
from app.models.import_batch import ImportBatch
from app.models.user import User
from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Helpers (same pattern as test_import_batch_endpoints.py)
# ---------------------------------------------------------------------------

def _create_user(firm_id: str, role: UserRole = UserRole.staff):
    email = f"patch-{uuid.uuid4().hex[:8]}@test.com"
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=uuid.UUID(firm_id),
            email=email,
            hashed_password=get_password_hash("testpass"),
            full_name="Patch Test",
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


def _add_member(firm_id: str, engagement_id: str, user_id: str, *, is_administrator: bool):
    db = TestingSessionLocal()
    try:
        db.add(EngagementMember(
            firm_id=uuid.UUID(firm_id),
            engagement_id=uuid.UUID(engagement_id),
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

    r = client.post("/clients/", json={"name": f"Patch-{uuid.uuid4().hex[:6]}"}, headers=headers)
    assert r.status_code == 201, r.text
    client_id = r.json()["id"]

    r = client.post("/engagements/", json={"name": f"Patch-Eng-{uuid.uuid4().hex[:6]}", "client_id": client_id}, headers=headers)
    assert r.status_code == 201, r.text
    eng_id = r.json()["id"]

    return firm_id, client_id, eng_id, headers


def _create_batch(client, headers, client_id, eng_id, conflict_policy="skip"):
    payload = {
        "scope": "engagement",
        "client_id": client_id,
        "engagement_id": eng_id,
        "conflict_policy": conflict_policy,
        "items": [{"relative_path": "file.pdf", "filename": "file.pdf", "expected_bytes": 512}],
    }
    r = client.post("/import-batches/", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _get_conflict_policy(batch_id: str) -> str:
    db = TestingSessionLocal()
    try:
        b = db.query(ImportBatch).filter(ImportBatch.id == uuid.UUID(batch_id)).first()
        v = b.conflict_policy
        return v.value if hasattr(v, "value") else str(v)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test (a): PATCH changes the policy on a draft batch
# ---------------------------------------------------------------------------

def test_patch_draft_batch_changes_conflict_policy(client, firm_a_owner):
    """PATCH on a draft batch successfully changes conflict_policy, and a
    subsequent GET reflects the updated value."""
    firm_id, client_id, eng_id, headers = _setup(client, firm_a_owner)
    batch = _create_batch(client, headers, client_id, eng_id, conflict_policy="skip")
    batch_id = batch["id"]

    assert batch["conflict_policy"] == "skip"

    r = client.patch(
        f"/import-batches/{batch_id}",
        json={"conflict_policy": "replace"},
        headers=headers,
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    assert r.json()["conflict_policy"] == "replace", (
        f"PATCH response shows wrong policy: {r.json()['conflict_policy']!r}"
    )

    # GET confirms the change persisted in the database.
    r2 = client.get(f"/import-batches/{batch_id}", headers=headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["conflict_policy"] == "replace", (
        f"GET after PATCH shows wrong policy: {r2.json()['conflict_policy']!r}"
    )

    # Direct DB read as final confirmation.
    assert _get_conflict_policy(batch_id) == "replace", (
        f"DB shows wrong policy after PATCH: {_get_conflict_policy(batch_id)!r}"
    )


# ---------------------------------------------------------------------------
# Test (b): PATCH on a confirmed batch is refused 422, policy unchanged
# ---------------------------------------------------------------------------

def test_patch_confirmed_batch_is_refused_422_and_policy_unchanged(client, firm_a_owner):
    """Attempting to PATCH a batch that has already been confirmed is refused
    422. The conflict_policy in the database is not modified.

    RED phase: temporarily remove the status check so the PATCH wrongly
    succeeds on a confirmed batch. Restore and confirm it is refused.
    """
    firm_id, client_id, eng_id, headers = _setup(client, firm_a_owner)
    batch = _create_batch(client, headers, client_id, eng_id, conflict_policy="skip")
    batch_id = batch["id"]

    # Confirm the batch so it is no longer in draft status.
    r = client.post(f"/import-batches/{batch_id}/confirm", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "confirmed"

    # --- RED phase: monkeypatch to remove the status check ---
    import app.services.import_batch_service as batch_svc
    from app.services.document_access import assert_can_bulk_import

    original_fn = batch_svc.update_batch_conflict_policy

    def _no_status_check(*, db, firm_id, batch_id, user, conflict_policy):
        """Broken version: skips the draft-status guard."""
        from sqlalchemy.orm import Session
        from app.models.import_batch import ImportBatch
        from app.models.import_item import ImportItem
        b = db.query(ImportBatch).filter(
            ImportBatch.id == batch_id,
            ImportBatch.firm_id == firm_id,
        ).first()
        if not b:
            raise HTTPException(status_code=404, detail="Import batch not found")
        assert_can_bulk_import(
            db=db, user=user, scope=b.scope,
            engagement_id=b.engagement_id, firm_id=firm_id,
        )
        # Missing status check -- this is the bug being demonstrated.
        b.conflict_policy = conflict_policy
        db.commit()
        db.refresh(b)
        items = db.query(ImportItem).filter(
            ImportItem.import_batch_id == batch_id,
            ImportItem.firm_id == firm_id,
        ).order_by(ImportItem.ordinal).all()
        return b, items

    batch_svc.update_batch_conflict_policy = _no_status_check
    try:
        r_red = client.patch(
            f"/import-batches/{batch_id}",
            json={"conflict_policy": "replace"},
            headers=headers,
        )
        assert r_red.status_code == 200, (
            f"RED: expected PATCH to wrongly succeed (200), got {r_red.status_code}"
        )
        assert _get_conflict_policy(batch_id) == "replace", (
            "RED: policy should have wrongly changed to 'replace', but did not"
        )
        # Watched-fail: if status check were present, this PATCH would return 422
        # with detail "Conflict policy can only be changed while the batch is in
        # draft status; current status is 'confirmed'"
    finally:
        batch_svc.update_batch_conflict_policy = original_fn
        # Restore the policy to "skip" so the green phase tests the real behavior.
        db = TestingSessionLocal()
        try:
            b = db.query(ImportBatch).filter(ImportBatch.id == uuid.UUID(batch_id)).first()
            b.conflict_policy = "skip"
            db.commit()
        finally:
            db.close()

    # --- GREEN phase: real function refuses PATCH on a confirmed batch ---
    r_green = client.patch(
        f"/import-batches/{batch_id}",
        json={"conflict_policy": "replace"},
        headers=headers,
    )
    assert r_green.status_code == 422, (
        f"Expected 422 for confirmed batch, got {r_green.status_code}: {r_green.text}"
    )
    detail = r_green.json()["detail"]
    assert "draft" in detail.lower(), (
        f"Expected 'draft' in detail, got: {detail!r}"
    )

    # Confirm the policy did not change in the database.
    assert _get_conflict_policy(batch_id) == "skip", (
        f"policy must remain 'skip' after refused PATCH; got {_get_conflict_policy(batch_id)!r}"
    )


# ---------------------------------------------------------------------------
# Test (c): auth check runs before status check
# ---------------------------------------------------------------------------

def test_patch_auth_check_runs_before_status_check(client, firm_a_owner):
    """An unauthorized plain staff member attempting to PATCH a batch in
    non-draft status must receive the permission refusal, not the status
    error, and must not learn the batch's real status.

    RED phase: temporarily swap checks so status fires before auth, confirming
    the wrong error exposes batch state. Restore and confirm auth fires first.
    """
    firm_id, client_id, eng_id, headers = _setup(client, firm_a_owner)
    batch = _create_batch(client, headers, client_id, eng_id)
    batch_id = batch["id"]

    # Confirm the batch so it has a non-draft status to potentially disclose.
    r = client.post(f"/import-batches/{batch_id}/confirm", headers=headers)
    assert r.status_code == 200, r.text

    # Plain staff user with no trio membership.
    noauth_email, _ = _create_user(firm_id, UserRole.staff)
    noauth_headers = _login(client, noauth_email)

    # --- RED phase: status check before auth ---
    import app.services.import_batch_service as batch_svc
    from app.services.document_access import assert_can_bulk_import

    original_fn = batch_svc.update_batch_conflict_policy

    def _wrong_order(*, db, firm_id, batch_id, user, conflict_policy):
        """Broken version: status check before auth -- exposes batch state."""
        from app.models.import_batch import ImportBatch
        b = db.query(ImportBatch).filter(
            ImportBatch.id == batch_id,
            ImportBatch.firm_id == firm_id,
        ).first()
        if not b:
            raise HTTPException(status_code=404, detail="Import batch not found")
        # WRONG ORDER: status before auth
        if b.status != "draft":
            raise HTTPException(
                status_code=422,
                detail=f"Conflict policy can only be changed while the batch is in draft status; current status is '{b.status}'",
            )
        assert_can_bulk_import(
            db=db, user=user, scope=b.scope,
            engagement_id=b.engagement_id, firm_id=firm_id,
        )
        b.conflict_policy = conflict_policy
        db.commit()
        return b, []

    batch_svc.update_batch_conflict_policy = _wrong_order
    try:
        r_red = client.patch(
            f"/import-batches/{batch_id}",
            json={"conflict_policy": "replace"},
            headers=noauth_headers,
        )
        assert r_red.status_code == 422, r_red.text
        detail_red = r_red.json()["detail"]
        # Wrong ordering: the status error fires first, leaking "confirmed" to an
        # unauthorized caller before they have been auth-checked.
        assert "confirmed" in detail_red, (
            f"RED: expected status error mentioning 'confirmed', got: {detail_red!r}"
        )
        assert "administrator" not in detail_red.lower(), (
            f"RED: permission error must not have fired yet, got: {detail_red!r}"
        )
    finally:
        batch_svc.update_batch_conflict_policy = original_fn

    # --- GREEN phase: real ordering -- permission error fires first ---
    r_green = client.patch(
        f"/import-batches/{batch_id}",
        json={"conflict_policy": "replace"},
        headers=noauth_headers,
    )
    assert r_green.status_code == 422, f"Expected 422, got {r_green.status_code}: {r_green.text}"
    detail_green = r_green.json()["detail"]

    assert "administrator" in detail_green.lower() or "manager" in detail_green.lower(), (
        f"Expected permission error, got: {detail_green!r}"
    )
    assert "confirmed" not in detail_green, (
        f"Batch status leaked to unauthorized caller: {detail_green!r}"
    )
    assert "draft" not in detail_green.lower(), (
        f"Batch status information leaked: {detail_green!r}"
    )
