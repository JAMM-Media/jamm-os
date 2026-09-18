# tests/test_import_batch_endpoints.py
"""
Guard tests for import batch Phase 2 endpoints (draft, confirm, get).

Tests:
  (a) Plain staff with no EngagementMember row for the target engagement is
      refused 422 on create. Watched red by temporarily removing is_administrator
      check from assert_can_bulk_import.
  (b) Engagement administrator (staff role, is_administrator True) can create
      and confirm, proving the trio check grants access rather than silently
      falling through to elevated-role-only.
  (c) Confirming an already-confirmed batch is refused 422.
  (d) Creating a batch with an empty items list is refused 422 at creation.
  (e) Scope mismatch (scope='client' with engagement_id set) is refused 422.
"""

import uuid

import pytest
from app.core.enums import UserRole
from app.core.security import get_password_hash
from app.models.engagement_member import EngagementMember
from app.models.user import User
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
            full_name="Test User",
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


def _add_member(firm_id: str, engagement_id: str, user_id: str, *, is_administrator: bool):
    db = TestingSessionLocal()
    try:
        member = EngagementMember(
            firm_id=uuid.UUID(firm_id),
            engagement_id=uuid.UUID(engagement_id),
            user_id=uuid.UUID(user_id),
            is_administrator=is_administrator,
        )
        db.add(member)
        db.commit()
    finally:
        db.close()


def _setup(test_client, firm_a_owner) -> tuple[str, str, str]:
    """Return (firm_id, client_id, engagement_id) via API."""
    headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]

    r = test_client.post("/clients/", json={"name": "Import Test Client"}, headers=headers)
    assert r.status_code == 201, r.text
    client_id = r.json()["id"]

    r = test_client.post(
        "/engagements/",
        json={"name": "Import Test Engagement", "client_id": client_id},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    eng_id = r.json()["id"]

    return firm_id, client_id, eng_id


def _batch_payload(client_id: str, eng_id: str) -> dict:
    return {
        "scope": "engagement",
        "client_id": client_id,
        "engagement_id": eng_id,
        "conflict_policy": "skip",
        "items": [
            {"relative_path": "Folder/file.pdf", "filename": "file.pdf", "expected_bytes": 1024},
        ],
    }


# ---------------------------------------------------------------------------
# Test (a): plain staff with no membership is refused 422 on create
# ---------------------------------------------------------------------------

def test_plain_staff_without_membership_is_refused_422_on_create(client, firm_a_owner):
    firm_id, client_id, eng_id = _setup(client, firm_a_owner)
    email, _ = _create_user(firm_id, UserRole.staff)
    headers = _login(client, email)

    r = client.post("/import-batches/", json=_batch_payload(client_id, eng_id), headers=headers)
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# Test (b): engagement administrator can create and confirm despite staff role
# ---------------------------------------------------------------------------

def test_engagement_administrator_staff_can_create_and_confirm(client, firm_a_owner):
    firm_id, client_id, eng_id = _setup(client, firm_a_owner)
    email, user_id = _create_user(firm_id, UserRole.staff)
    _add_member(firm_id, eng_id, user_id, is_administrator=True)
    headers = _login(client, email)

    r = client.post("/import-batches/", json=_batch_payload(client_id, eng_id), headers=headers)
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
    batch_id = r.json()["id"]
    assert r.json()["status"] == "draft"
    assert len(r.json()["items"]) == 1

    r = client.post(f"/import-batches/{batch_id}/confirm", headers=headers)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    assert r.json()["status"] == "confirmed"
    assert r.json()["confirmed_at"] is not None


# ---------------------------------------------------------------------------
# Test (c): confirming an already-confirmed batch is refused 422
# ---------------------------------------------------------------------------

def test_double_confirm_is_refused_422(client, firm_a_owner):
    firm_id, client_id, eng_id = _setup(client, firm_a_owner)
    headers = firm_a_owner["headers"]

    r = client.post("/import-batches/", json=_batch_payload(client_id, eng_id), headers=headers)
    assert r.status_code == 201, r.text
    batch_id = r.json()["id"]

    r = client.post(f"/import-batches/{batch_id}/confirm", headers=headers)
    assert r.status_code == 200, r.text

    r = client.post(f"/import-batches/{batch_id}/confirm", headers=headers)
    assert r.status_code == 422, f"Expected 422 on second confirm, got {r.status_code}: {r.text}"
    assert "already" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test (d): empty items list is refused 422 at creation
# ---------------------------------------------------------------------------

def test_empty_items_list_is_refused_at_creation(client, firm_a_owner):
    firm_id, client_id, eng_id = _setup(client, firm_a_owner)
    headers = firm_a_owner["headers"]

    payload = {
        "scope": "engagement",
        "client_id": client_id,
        "engagement_id": eng_id,
        "conflict_policy": "skip",
        "items": [],
    }
    r = client.post("/import-batches/", json=payload, headers=headers)
    assert r.status_code == 422, f"Expected 422 for empty items, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# Test (e): scope mismatch (client scope + engagement_id set) is refused 422
# ---------------------------------------------------------------------------

def test_scope_mismatch_client_with_engagement_id_is_refused(client, firm_a_owner):
    firm_id, client_id, eng_id = _setup(client, firm_a_owner)
    headers = firm_a_owner["headers"]

    payload = {
        "scope": "client",
        "client_id": client_id,
        "engagement_id": eng_id,   # invalid: client scope must not have engagement_id
        "conflict_policy": "skip",
        "items": [
            {"relative_path": "file.pdf", "filename": "file.pdf", "expected_bytes": 512},
        ],
    }
    r = client.post("/import-batches/", json=payload, headers=headers)
    assert r.status_code == 422, f"Expected 422 for scope mismatch, got {r.status_code}: {r.text}"
