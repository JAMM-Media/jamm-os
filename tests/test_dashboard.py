# tests/test_dashboard.py

import pytest
from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_manager(firm_id, client):
    from app.models.user import User
    from app.core.security import get_password_hash
    from app.core.enums import UserRole
    import uuid

    email = f"manager-{uuid.uuid4()}@firma.com"
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=email,
            hashed_password=get_password_hash("managerpass123"),
            full_name="Manager A",
            role=UserRole.manager,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    login = client.post("/auth/token", json={"username": email, "password": "managerpass123"})
    assert login.status_code == 200, f"Manager login failed: {login.json()}"
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_dashboard_metrics_requires_auth(client):
    r = client.get("/dashboard/metrics")
    assert r.status_code == 401


def test_dashboard_metrics_staff_forbidden(client, firm_a_staff):
    r = client.get("/dashboard/metrics", headers=firm_a_staff["headers"])
    assert r.status_code == 403


def test_dashboard_metrics_manager_success(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    headers = _make_manager(firm_id, client)

    r = client.get("/dashboard/metrics", headers=headers)
    assert r.status_code == 200

    data = r.json()
    expected_keys = {
        "mrr",
        "mrr_invoice_count",
        "outstanding_ar",
        "outstanding_ar_count",
        "oldest_overdue_days",
        "wip_value",
        "wip_hours",
        "overdue_engagement_count",
        "overdue_engagements",
        "upcoming_deadlines",
        "staff_utilization",
        "unsigned_document_count",
        "unsigned_documents",
    }
    assert expected_keys.issubset(data.keys())
    assert isinstance(data["mrr"], float)
    assert isinstance(data["overdue_engagements"], list)
    assert isinstance(data["upcoming_deadlines"], list)
    assert isinstance(data["staff_utilization"], list)
    assert isinstance(data["unsigned_documents"], list)


def test_dashboard_metrics_tenant_isolation(client, firm_a_owner, firm_b_owner):
    """Firm A manager cannot see Firm B's data."""
    from app.models.client import Client
    from app.models.invoice import Invoice
    from app.core.enums import InvoiceStatus
    from datetime import datetime, timezone
    import uuid

    # Create a paid invoice in Firm B this month
    firm_b_id = firm_b_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        b_client = Client(firm_id=firm_b_id, name="Firm B Client")
        db.add(b_client)
        db.commit()
        db.refresh(b_client)

        invoice = Invoice(
            firm_id=firm_b_id,
            client_id=b_client.id,
            invoice_number="INV-B-001",
            subtotal=5000.0,
            tax_rate=0.0,
            tax_amount=0.0,
            total_amount=5000.0,
            status=InvoiceStatus.paid,
            paid_at=datetime.now(timezone.utc),
        )
        db.add(invoice)
        db.commit()
    finally:
        db.close()

    # Firm A manager should see mrr = 0, not Firm B's $5000
    firm_a_id = firm_a_owner["firm_id"]
    headers = _make_manager(firm_a_id, client)

    r = client.get("/dashboard/metrics", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["mrr"] == 0.0, "Firm A should not see Firm B's revenue"
    assert data["outstanding_ar_count"] == 0
