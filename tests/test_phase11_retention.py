# tests/test_phase11_retention.py

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.user import User
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.document import Document
from app.models.retention import DataRetentionPolicy
from app.core.security import get_password_hash
from app.core.enums import UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_staff_in_firm(client_fixture, firm_id: uuid.UUID) -> dict:
    """Create a staff user in the given firm, return auth headers."""
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=f"staff-ret-{uuid.uuid4().hex[:6]}@firma.com",
            hashed_password=get_password_hash("staffpass"),
            full_name="Staff",
            role=UserRole.staff,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        email = user.email
    finally:
        db.close()

    login = client_fixture.post("/auth/token", json={"username": email, "password": "staffpass"})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_document_in_firm(firm_id: uuid.UUID) -> uuid.UUID:
    """Create a client, engagement, and document in the given firm. Returns doc id."""
    db = TestingSessionLocal()
    try:
        client_obj = Client(firm_id=firm_id, name="Retention Test Client", email=f"ret-{uuid.uuid4().hex[:8]}@client.com")
        db.add(client_obj)
        db.commit()
        db.refresh(client_obj)

        eng = Engagement(
            firm_id=firm_id,
            client_id=client_obj.id,
            name="Retention Engagement",
        )
        db.add(eng)
        db.commit()
        db.refresh(eng)

        doc = Document(
            firm_id=firm_id,
            client_id=client_obj.id,
            engagement_id=eng.id,
            filename="test.pdf",
            s3_key=f"{firm_id}/{uuid.uuid4()}/test.pdf",
            content_type="application/pdf",
            size_bytes=1024,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc.id
    finally:
        db.close()


def _backdate_document(doc_id: uuid.UUID, years_ago: int) -> None:
    """Manually set a document's created_at to N years in the past."""
    old_date = datetime.now(timezone.utc) - timedelta(days=years_ago * 365)
    db = TestingSessionLocal()
    try:
        db.execute(
            text("UPDATE documents SET created_at = :dt WHERE id = :id"),
            {"dt": old_date, "id": str(doc_id)},
        )
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 1: GET /retention/policy when no policy exists → creates default
# ---------------------------------------------------------------------------
def test_get_retention_policy_creates_default(client, firm_a_owner):
    r = client.get("/retention/policy", headers=firm_a_owner["headers"])
    assert r.status_code == 200
    data = r.json()
    assert data["document_retention_years"] == 7
    assert data["auto_flag_enabled"] is True
    assert data["firm_id"] == firm_a_owner["firm_id"]


# ---------------------------------------------------------------------------
# Test 2: GET /retention/policy when policy exists → returns existing, no duplicate
# ---------------------------------------------------------------------------
def test_get_retention_policy_no_duplicate(client, firm_a_owner):
    # First call creates the policy
    r1 = client.get("/retention/policy", headers=firm_a_owner["headers"])
    assert r1.status_code == 200
    id1 = r1.json()["id"]

    # Second call should return the same record
    r2 = client.get("/retention/policy", headers=firm_a_owner["headers"])
    assert r2.status_code == 200
    assert r2.json()["id"] == id1

    # Confirm only one policy in DB
    db = TestingSessionLocal()
    try:
        count = db.query(DataRetentionPolicy).filter(
            DataRetentionPolicy.firm_id == uuid.UUID(firm_a_owner["firm_id"])
        ).count()
        assert count == 1
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 3: PUT /retention/policy updates document_retention_years
# ---------------------------------------------------------------------------
def test_update_retention_years(client, firm_a_owner):
    r = client.put(
        "/retention/policy",
        json={"document_retention_years": 10},
        headers=firm_a_owner["headers"],
    )
    assert r.status_code == 200
    assert r.json()["document_retention_years"] == 10


# ---------------------------------------------------------------------------
# Test 4: PUT /retention/policy updates auto_flag_enabled
# ---------------------------------------------------------------------------
def test_update_auto_flag_enabled(client, firm_a_owner):
    r = client.put(
        "/retention/policy",
        json={"auto_flag_enabled": False},
        headers=firm_a_owner["headers"],
    )
    assert r.status_code == 200
    assert r.json()["auto_flag_enabled"] is False


# ---------------------------------------------------------------------------
# Test 5: GET /retention/flagged returns empty list for recent documents
# ---------------------------------------------------------------------------
def test_flagged_empty_for_recent_documents(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _create_document_in_firm(firm_id)  # created right now

    r = client.get("/retention/flagged", headers=firm_a_owner["headers"])
    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# Test 6: GET /retention/flagged returns backdated document
# ---------------------------------------------------------------------------
def test_flagged_returns_old_document(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])

    # Create a document and backdate it to 8 years ago
    doc_id = _create_document_in_firm(firm_id)
    _backdate_document(doc_id, years_ago=8)

    # Ensure policy is 7 years
    client.put(
        "/retention/policy",
        json={"document_retention_years": 7},
        headers=firm_a_owner["headers"],
    )

    r = client.get("/retention/flagged", headers=firm_a_owner["headers"])
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    flagged_ids = [item["id"] for item in data]
    assert str(doc_id) in flagged_ids
    # Check reason string
    for item in data:
        assert "retention_flag_reason" in item
        assert "7" in item["retention_flag_reason"]


# ---------------------------------------------------------------------------
# Test 7: POST /retention/run-check returns correct flagged_count + updates last_ran_at
# ---------------------------------------------------------------------------
def test_run_check_updates_last_ran_at(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])

    # Backdate a document to be older than retention period
    doc_id = _create_document_in_firm(firm_id)
    _backdate_document(doc_id, years_ago=9)

    r = client.post("/retention/run-check", headers=firm_a_owner["headers"])
    assert r.status_code == 200
    data = r.json()
    assert data["flagged_count"] >= 1
    assert str(doc_id) in data["flagged_document_ids"]
    assert data["firm_id"] == firm_a_owner["firm_id"]

    # Verify last_ran_at is now set
    r2 = client.get("/retention/policy", headers=firm_a_owner["headers"])
    assert r2.json()["last_ran_at"] is not None


# ---------------------------------------------------------------------------
# Test 8: Staff role gets 403 on all retention endpoints
# ---------------------------------------------------------------------------
def test_staff_gets_403_on_retention_endpoints(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    staff_headers = _make_staff_in_firm(client, firm_id)

    assert client.get("/retention/policy", headers=staff_headers).status_code == 403
    assert client.put("/retention/policy", json={"document_retention_years": 5}, headers=staff_headers).status_code == 403
    assert client.get("/retention/flagged", headers=staff_headers).status_code == 403
    assert client.post("/retention/run-check", headers=staff_headers).status_code == 403


# ---------------------------------------------------------------------------
# Test 9: Firm A cannot see Firm B's flagged documents (tenant isolation)
# ---------------------------------------------------------------------------
def test_retention_tenant_isolation(client, firm_a_owner, firm_b_owner):
    firm_a_id = uuid.UUID(firm_a_owner["firm_id"])
    firm_b_id = uuid.UUID(firm_b_owner["firm_id"])

    # Backdate a document in each firm
    doc_a = _create_document_in_firm(firm_a_id)
    doc_b = _create_document_in_firm(firm_b_id)
    _backdate_document(doc_a, years_ago=8)
    _backdate_document(doc_b, years_ago=8)

    # Firm A's flagged list should only contain firm_a's doc
    r_a = client.get("/retention/flagged", headers=firm_a_owner["headers"])
    assert r_a.status_code == 200
    ids_a = [item["id"] for item in r_a.json()]
    assert str(doc_a) in ids_a
    assert str(doc_b) not in ids_a

    # Firm B's flagged list should only contain firm_b's doc
    r_b = client.get("/retention/flagged", headers=firm_b_owner["headers"])
    assert r_b.status_code == 200
    ids_b = [item["id"] for item in r_b.json()]
    assert str(doc_b) in ids_b
    assert str(doc_a) not in ids_b
