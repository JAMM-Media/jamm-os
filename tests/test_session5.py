# tests/test_session5.py

"""
Session 5 tests: WIP Report, Bulk Actions, Calendar.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.conftest import TestingSessionLocal
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.firm import Firm
from app.models.invoice import Invoice
from app.models.task import Task
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.core.security import get_password_hash
from app.core.enums import UserRole, InvoiceStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm_and_owner(slug=None, email=None):
    slug = slug or f"firm-{uuid.uuid4().hex[:8]}"
    email = email or f"owner-{uuid.uuid4().hex[:8]}@test.com"
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Test Firm {slug}", slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)

        from app.services.tax_organizer_service import seed_firm_organizer_templates
        seed_firm_organizer_templates(firm_id=firm.id, db=db)

        user = User(
            firm_id=firm.id,
            email=email,
            hashed_password=get_password_hash("testpass123"),
            full_name="Test Owner",
            role=UserRole.firm_owner,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        firm_id = firm.id
        user_id = user.id
    finally:
        db.close()
    return firm_id, user_id, email


def _login(http_client, email, password="testpass123"):
    r = http_client.post("/auth/token", json={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_client(firm_id):
    db = TestingSessionLocal()
    try:
        c = Client(
            firm_id=firm_id,
            name="WIP Client",
            email=f"c-{uuid.uuid4().hex[:8]}@client.com",
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        cid = c.id
    finally:
        db.close()
    return cid


def _make_engagement(firm_id, client_id, *, status="active", filing_deadline=None, extended_deadline=None):
    db = TestingSessionLocal()
    try:
        eng = Engagement(
            firm_id=firm_id,
            client_id=client_id,
            name=f"Eng-{uuid.uuid4().hex[:6]}",
            status=status,
            filing_deadline=filing_deadline,
            extended_deadline=extended_deadline,
        )
        db.add(eng)
        db.commit()
        db.refresh(eng)
        eid = eng.id
    finally:
        db.close()
    return eid


def _make_time_entry(firm_id, engagement_id, user_id, *, is_billed=False, is_billable=True, hours=2.0, hourly_rate=100.0):
    db = TestingSessionLocal()
    try:
        te = TimeEntry(
            firm_id=firm_id,
            engagement_id=engagement_id,
            user_id=user_id,
            description="Test work",
            hours=Decimal(str(hours)),
            hourly_rate=Decimal(str(hourly_rate)),
            is_billable=is_billable,
            is_billed=is_billed,
            date=date.today(),
        )
        db.add(te)
        db.commit()
        db.refresh(te)
        tid = te.id
    finally:
        db.close()
    return tid


def _make_task(firm_id, client_id, engagement_id, *, status="todo"):
    db = TestingSessionLocal()
    try:
        t = Task(
            firm_id=firm_id,
            client_id=client_id,
            engagement_id=engagement_id,
            title=f"Task-{uuid.uuid4().hex[:6]}",
            status=status,
        )
        db.add(t)
        db.commit()
        db.refresh(t)
        tid = t.id
    finally:
        db.close()
    return tid


def _make_invoice(firm_id, client_id, *, status=InvoiceStatus.sent):
    db = TestingSessionLocal()
    try:
        inv = Invoice(
            firm_id=firm_id,
            client_id=client_id,
            invoice_number=f"INV-{uuid.uuid4().hex[:8]}",
            line_items=[],
            subtotal=Decimal("500.00"),
            tax_rate=Decimal("0.0"),
            tax_amount=Decimal("0.0"),
            total_amount=Decimal("500.00"),
            status=status,
        )
        db.add(inv)
        db.commit()
        db.refresh(inv)
        iid = inv.id
    finally:
        db.close()
    return iid


# ===========================================================================
# 5A — WIP Report
# ===========================================================================

def test_wip_report_returns_unbilled_entries(client):
    firm_id, user_id, email = _make_firm_and_owner()
    headers = _login(client, email)
    client_id = _make_client(firm_id)
    eng_id = _make_engagement(firm_id, client_id)
    _make_time_entry(firm_id, eng_id, user_id, is_billed=False, is_billable=True, hours=3.0, hourly_rate=200.0)

    r = client.get("/reports/wip", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert Decimal(str(data["total_wip_value"])) == Decimal("600.00")
    assert Decimal(str(data["total_hours"])) == Decimal("3.0")
    assert len(data["top_engagements"]) >= 1


def test_wip_report_excludes_billed(client):
    firm_id, user_id, email = _make_firm_and_owner()
    headers = _login(client, email)
    client_id = _make_client(firm_id)
    eng_id = _make_engagement(firm_id, client_id)
    _make_time_entry(firm_id, eng_id, user_id, is_billed=True, is_billable=True, hours=5.0, hourly_rate=100.0)
    _make_time_entry(firm_id, eng_id, user_id, is_billed=False, is_billable=True, hours=2.0, hourly_rate=100.0)

    r = client.get("/reports/wip", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert Decimal(str(data["total_wip_value"])) == Decimal("200.00")
    assert Decimal(str(data["total_hours"])) == Decimal("2.0")


# ===========================================================================
# 5B — Bulk Actions
# ===========================================================================

def test_bulk_task_status_update(client):
    firm_id, user_id, email = _make_firm_and_owner()
    headers = _login(client, email)
    client_id = _make_client(firm_id)
    eng_id = _make_engagement(firm_id, client_id)

    task_ids = [
        str(_make_task(firm_id, client_id, eng_id, status="todo"))
        for _ in range(3)
    ]

    r = client.patch(
        "/tasks/bulk",
        json={"ids": task_ids, "update": {"status": "in_progress"}},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["updated"] == 3

    db = TestingSessionLocal()
    try:
        for tid in task_ids:
            task = db.get(Task, uuid.UUID(tid))
            assert task is not None
            assert task.status == "in_progress"
    finally:
        db.close()


def test_bulk_actions_tenant_isolation(client):
    firm_a_id, user_a_id, email_a = _make_firm_and_owner()
    firm_b_id, user_b_id, email_b = _make_firm_and_owner()
    headers_a = _login(client, email_a)

    client_a_id = _make_client(firm_a_id)
    eng_a_id = _make_engagement(firm_a_id, client_a_id)
    task_a_id = str(_make_task(firm_a_id, client_a_id, eng_a_id, status="todo"))

    client_b_id = _make_client(firm_b_id)
    eng_b_id = _make_engagement(firm_b_id, client_b_id)
    task_b_id = str(_make_task(firm_b_id, client_b_id, eng_b_id, status="todo"))

    r = client.patch(
        "/tasks/bulk",
        json={"ids": [task_a_id, task_b_id], "update": {"status": "done"}},
        headers=headers_a,
    )
    assert r.status_code == 200, r.text
    assert r.json()["updated"] == 1

    db = TestingSessionLocal()
    try:
        task_b = db.get(Task, uuid.UUID(task_b_id))
        assert task_b.status == "todo"
    finally:
        db.close()


def test_bulk_engagement_deadline_push(client):
    firm_id, user_id, email = _make_firm_and_owner()
    headers = _login(client, email)
    client_id = _make_client(firm_id)
    today = date.today()
    filing = today + timedelta(days=30)
    eng_id = str(_make_engagement(firm_id, client_id, filing_deadline=filing))

    r = client.patch(
        "/engagements/bulk",
        json={"ids": [eng_id], "update": {"deadline_push_days": 7}},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["updated"] == 1

    db = TestingSessionLocal()
    try:
        eng = db.get(Engagement, uuid.UUID(eng_id))
        assert eng.filing_deadline == filing + timedelta(days=7)
    finally:
        db.close()


def test_bulk_invoice_void(client):
    firm_id, user_id, email = _make_firm_and_owner()
    headers = _login(client, email)
    client_id = _make_client(firm_id)
    inv_id = str(_make_invoice(firm_id, client_id, status=InvoiceStatus.sent))

    r = client.patch(
        "/invoices/bulk",
        json={"ids": [inv_id], "action": "void"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["updated"] == 1

    db = TestingSessionLocal()
    try:
        inv = db.get(Invoice, uuid.UUID(inv_id))
        assert inv.status == InvoiceStatus.void
    finally:
        db.close()


# ===========================================================================
# 5C — Calendar
# ===========================================================================

def test_calendar_returns_upcoming_deadlines(client):
    firm_id, user_id, email = _make_firm_and_owner()
    headers = _login(client, email)
    client_id = _make_client(firm_id)
    filing = date.today() + timedelta(days=30)
    eng_id = str(_make_engagement(firm_id, client_id, status="active", filing_deadline=filing))

    r = client.get("/engagements/calendar", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    ids = [item["engagement_id"] for item in data.get("items", [])]
    assert eng_id in ids


def test_calendar_excludes_completed(client):
    firm_id, user_id, email = _make_firm_and_owner()
    headers = _login(client, email)
    client_id = _make_client(firm_id)
    filing = date.today() + timedelta(days=30)
    eng_id = str(_make_engagement(firm_id, client_id, status="completed", filing_deadline=filing))

    r = client.get("/engagements/calendar", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    ids = [item["engagement_id"] for item in data.get("items", [])]
    assert eng_id not in ids
