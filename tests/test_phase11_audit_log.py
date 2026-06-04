# tests/test_phase11_audit_log.py

import uuid
from datetime import date, timedelta

import pytest
from tests.conftest import TestingSessionLocal
from app.models.audit_log import AuditLog
from app.models.firm import Firm
from app.models.user import User
from app.core.security import get_password_hash
from app.core.enums import UserRole
from app.services.audit_service import write_audit_log


# ---------------------------------------------------------------------------
# Test 1 — write_audit_log() creates a record with correct fields
# ---------------------------------------------------------------------------
def test_write_audit_log_creates_record():
    db = TestingSessionLocal()
    try:
        firm = Firm(name="Audit Firm", slug="audit-firm-1")
        db.add(firm)
        db.commit()
        db.refresh(firm)

        user = User(
            firm_id=firm.id,
            email="actor@auditfirm.com",
            hashed_password=get_password_hash("password"),
            full_name="Actor",
            role=UserRole.staff,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        write_audit_log(
            db=db,
            firm_id=firm.id,
            action="user.login_success",
            actor_id=user.id,
            actor_type="staff",
            entity_type="user",
            entity_id=user.id,
            ip_address="127.0.0.1",
            user_agent="test-agent",
            metadata={"key": "value"},
        )

        record = db.query(AuditLog).filter(
            AuditLog.firm_id == firm.id,
            AuditLog.action == "user.login_success",
        ).first()

        assert record is not None
        assert record.actor_id == user.id
        assert record.actor_type == "staff"
        assert record.entity_type == "user"
        assert record.entity_id == user.id
        assert record.ip_address == "127.0.0.1"
        assert record.user_agent == "test-agent"
        assert record.extra_metadata == {"key": "value"}
        assert record.created_at is not None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 2 — write_audit_log() does not raise on bad/missing data (resilience)
# ---------------------------------------------------------------------------
def test_write_audit_log_resilience():
    db = TestingSessionLocal()
    try:
        firm = Firm(name="Resilience Firm", slug="resilience-firm-1")
        db.add(firm)
        db.commit()
        db.refresh(firm)

        # Pass a non-existent actor_id (FK violation) — should not raise
        write_audit_log(
            db=db,
            firm_id=firm.id,
            action="test.event",
            actor_id=uuid.uuid4(),  # non-existent user
            actor_type="staff",
        )
        # If we get here without exception, the test passes.
        # The record may not have been created, but no crash occurred.
    except Exception as exc:
        pytest.fail(f"write_audit_log raised unexpectedly: {exc}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 3 — GET /admin/audit-logs returns only records for the authenticated firm
# ---------------------------------------------------------------------------
def test_admin_audit_logs_scoped_to_firm(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    db = TestingSessionLocal()
    try:
        # Create a record for Firm A
        entry = AuditLog(
            firm_id=firm_id,
            action="test.event",
            actor_type="system",
        )
        db.add(entry)
        db.commit()
    finally:
        db.close()

    resp = client.get("/admin/audit-logs", headers=firm_a_owner["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["firm_id"] == str(firm_id)


# ---------------------------------------------------------------------------
# Test 4 — GET /admin/audit-logs filtered by action= returns only matching records
# ---------------------------------------------------------------------------
def test_admin_audit_logs_filter_by_action(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    db = TestingSessionLocal()
    try:
        db.add(AuditLog(firm_id=firm_id, action="document.uploaded", actor_type="staff"))
        db.add(AuditLog(firm_id=firm_id, action="user.login_success", actor_type="staff"))
        db.commit()
    finally:
        db.close()

    resp = client.get(
        "/admin/audit-logs?action=document.uploaded",
        headers=firm_a_owner["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["action"] == "document.uploaded"


# ---------------------------------------------------------------------------
# Test 5 — GET /admin/audit-logs filtered by start_date/end_date returns correct range
# ---------------------------------------------------------------------------
def test_admin_audit_logs_filter_by_date_range(client, firm_a_owner):
    from sqlalchemy import text
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    db = TestingSessionLocal()
    try:
        # Insert one old record and one recent record
        db.execute(
            text(
                "INSERT INTO audit_logs (id, firm_id, action, actor_type, created_at) "
                "VALUES (:id, :firm_id, 'old.event', 'system', '2020-01-01 00:00:00+00')"
            ),
            {"id": str(uuid.uuid4()), "firm_id": str(firm_id)},
        )
        db.execute(
            text(
                "INSERT INTO audit_logs (id, firm_id, action, actor_type, created_at) "
                "VALUES (:id, :firm_id, 'new.event', 'system', now())"
            ),
            {"id": str(uuid.uuid4()), "firm_id": str(firm_id)},
        )
        db.commit()
    finally:
        db.close()

    # Query for only the old record
    resp = client.get(
        "/admin/audit-logs?start_date=2019-12-31&end_date=2020-01-02",
        headers=firm_a_owner["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["action"] == "old.event"

    # Query for only recent records (after 2021)
    today = date.today().isoformat()
    resp2 = client.get(
        f"/admin/audit-logs?start_date=2021-01-01&end_date={today}",
        headers=firm_a_owner["headers"],
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    for item in data2["items"]:
        assert item["action"] != "old.event"


# ---------------------------------------------------------------------------
# Test 6 — Staff role (non-owner) gets 403 on GET /admin/audit-logs
# ---------------------------------------------------------------------------
def test_admin_audit_logs_staff_gets_403(client, firm_a_owner):
    # Create a staff user in Firm A
    db = TestingSessionLocal()
    try:
        firm_id = uuid.UUID(firm_a_owner["firm_id"])
        staff = User(
            firm_id=firm_id,
            email="staff_audit@firma.com",
            hashed_password=get_password_hash("staffpass"),
            full_name="Staff",
            role=UserRole.staff,
        )
        db.add(staff)
        db.commit()
    finally:
        db.close()

    login = client.post(
        "/auth/token",
        json={"username": "staff_audit@firma.com", "password": "staffpass"},
    )
    token = login.json()["access_token"]
    staff_headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/admin/audit-logs", headers=staff_headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test 7 — Firm A cannot see Firm B's audit log records (tenant isolation)
# ---------------------------------------------------------------------------
def test_admin_audit_logs_tenant_isolation(client, firm_a_owner, firm_b_owner):
    firm_a_id = uuid.UUID(firm_a_owner["firm_id"])
    firm_b_id = uuid.UUID(firm_b_owner["firm_id"])

    db = TestingSessionLocal()
    try:
        db.add(AuditLog(firm_id=firm_a_id, action="firma.event", actor_type="staff"))
        db.add(AuditLog(firm_id=firm_b_id, action="firmb.event", actor_type="staff"))
        db.commit()
    finally:
        db.close()

    # Firm A owner queries — should only see Firm A record
    resp_a = client.get("/admin/audit-logs", headers=firm_a_owner["headers"])
    assert resp_a.status_code == 200
    for item in resp_a.json()["items"]:
        assert item["firm_id"] == str(firm_a_id)
        assert item["action"] != "firmb.event"

    # Firm B owner queries — should only see Firm B record
    resp_b = client.get("/admin/audit-logs", headers=firm_b_owner["headers"])
    assert resp_b.status_code == 200
    for item in resp_b.json()["items"]:
        assert item["firm_id"] == str(firm_b_id)
        assert item["action"] != "firma.event"
