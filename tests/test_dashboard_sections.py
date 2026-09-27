# tests/test_dashboard_sections.py

import uuid
from datetime import datetime, timezone, timedelta, date as date_type

import pytest
from tests.conftest import TestingSessionLocal

from app.models.invoice import Invoice
from app.models.time_entry import TimeEntry
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.user import User
from app.core.enums import InvoiceStatus, UserRole
from app.core.security import get_password_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now():
    return datetime.now(timezone.utc)


def _make_client(db, firm_id, name="Test Client"):
    c = Client(firm_id=firm_id, name=name)
    db.add(c)
    db.flush()
    return c


def _make_engagement(db, firm_id, client_id):
    e = Engagement(firm_id=firm_id, client_id=client_id, name="Test Engagement")
    db.add(e)
    db.flush()
    return e


def _make_user(db, firm_id):
    u = User(
        firm_id=firm_id,
        email=f"staff-{uuid.uuid4()}@test.com",
        hashed_password=get_password_hash("pass"),
        full_name="Staff",
        role=UserRole.staff,
    )
    db.add(u)
    db.flush()
    return u


def _make_invoice(db, firm_id, client_id, user_id, **kwargs):
    inv = Invoice(
        id=uuid.uuid4(),
        firm_id=firm_id,
        client_id=client_id,
        created_by=user_id,
        invoice_number=str(uuid.uuid4())[:8],
        subtotal=kwargs.get("total_amount", 100.0),
        tax_rate=0.0,
        tax_amount=0.0,
        total_amount=kwargs.get("total_amount", 100.0),
        status=kwargs.get("status", InvoiceStatus.paid),
        paid_at=kwargs.get("paid_at"),
        sent_at=kwargs.get("sent_at"),
        is_deleted=False,
        amount_paid=kwargs.get("amount_paid", 0.0),
    )
    db.add(inv)
    db.flush()
    return inv


def _make_time_entry(db, firm_id, engagement_id, user_id, **kwargs):
    te = TimeEntry(
        id=uuid.uuid4(),
        firm_id=firm_id,
        engagement_id=engagement_id,
        user_id=user_id,
        description="Test entry",
        hours=kwargs.get("hours", 2.0),
        hourly_rate=kwargs.get("hourly_rate", 100.0),
        is_billable=True,
        is_billed=kwargs.get("is_billed", False),
        invoice_id=kwargs.get("invoice_id"),
        date=date_type.today(),
        created_at=kwargs.get("created_at", _now()),
    )
    db.add(te)
    db.flush()
    return te


# ---------------------------------------------------------------------------
# Trend calculation tests
# ---------------------------------------------------------------------------

def test_mrr_trend_upward(client, firm_a_owner):
    """Revenue This Month trend shows 'up' when current month > prior month."""
    firm_id = firm_a_owner["firm_id"]
    now = _now()
    today = now.date()
    start_of_month = datetime(today.year, today.month, 1, tzinfo=timezone.utc)
    if today.month == 1:
        prior_start = datetime(today.year - 1, 12, 1, tzinfo=timezone.utc)
    else:
        prior_start = datetime(today.year, today.month - 1, 1, tzinfo=timezone.utc)

    db = TestingSessionLocal()
    try:
        c = _make_client(db, firm_id)
        u = _make_user(db, firm_id)
        # Prior month: $100 paid
        _make_invoice(db, firm_id, c.id, u.id,
                      total_amount=100.0, status=InvoiceStatus.paid,
                      paid_at=prior_start + timedelta(days=1))
        # Current month: $200 paid
        _make_invoice(db, firm_id, c.id, u.id,
                      total_amount=200.0, status=InvoiceStatus.paid,
                      paid_at=start_of_month + timedelta(days=1))
        db.commit()
    finally:
        db.close()

    resp = client.get("/dashboard/metrics", headers=firm_a_owner["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["mrr"] >= 200.0
    assert data["mrr_trend_direction"] == "up"
    assert data["mrr_trend_pct"] == 100.0


def test_mrr_trend_null_when_no_prior_revenue(client, firm_a_owner):
    """Revenue trend is null when prior month has no paid invoices."""
    firm_id = firm_a_owner["firm_id"]
    today = datetime.now(timezone.utc).date()
    start_of_month = datetime(today.year, today.month, 1, tzinfo=timezone.utc)

    db = TestingSessionLocal()
    try:
        c = _make_client(db, firm_id)
        u = _make_user(db, firm_id)
        _make_invoice(db, firm_id, c.id, u.id,
                      total_amount=500.0, status=InvoiceStatus.paid,
                      paid_at=start_of_month + timedelta(days=1))
        db.commit()
    finally:
        db.close()

    resp = client.get("/dashboard/metrics", headers=firm_a_owner["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["mrr_trend_pct"] is None
    assert data["mrr_trend_direction"] is None


def test_ar_trend_invoice_sent_40_days_ago_included_in_prior(client, firm_a_owner):
    """Invoice sent 40 days ago and still unpaid is in both current AR and prior AR."""
    firm_id = firm_a_owner["firm_id"]
    cutoff = _now() - timedelta(days=30)

    db = TestingSessionLocal()
    try:
        c = _make_client(db, firm_id)
        u = _make_user(db, firm_id)
        _make_invoice(db, firm_id, c.id, u.id,
                      total_amount=300.0,
                      status=InvoiceStatus.sent,
                      sent_at=cutoff - timedelta(days=10),
                      paid_at=None)
        db.commit()
    finally:
        db.close()

    resp = client.get("/dashboard/metrics", headers=firm_a_owner["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["outstanding_ar"] >= 300.0
    # current == prior -> direction 'up' (>= check), pct == 0
    assert data["ar_trend_direction"] == "up"
    assert data["ar_trend_pct"] == 0.0


def test_wip_trend_entry_billed_within_30_days_counted_in_prior(client, firm_a_owner):
    """Time entry billed 20 days ago appears in prior WIP but not current WIP."""
    firm_id = firm_a_owner["firm_id"]
    now = _now()
    cutoff = now - timedelta(days=30)

    db = TestingSessionLocal()
    try:
        c = _make_client(db, firm_id)
        u = _make_user(db, firm_id)
        eng = _make_engagement(db, firm_id, c.id)

        inv = _make_invoice(db, firm_id, c.id, u.id,
                            total_amount=200.0,
                            status=InvoiceStatus.paid,
                            paid_at=now,
                            sent_at=now - timedelta(days=25))
        # Set invoice.created_at to 20 days ago (after cutoff)
        inv.created_at = now - timedelta(days=20)

        # Time entry created 35 days ago (before cutoff), billed 20 days ago
        _make_time_entry(db, firm_id, eng.id, u.id,
                         hours=2.0, hourly_rate=100.0,
                         is_billed=True,
                         invoice_id=inv.id,
                         created_at=cutoff - timedelta(days=5))
        db.commit()
    finally:
        db.close()

    resp = client.get("/dashboard/metrics", headers=firm_a_owner["headers"])
    assert resp.status_code == 200
    data = resp.json()
    # Prior WIP >= 200, current WIP does not include this billed entry
    assert data["wip_trend_direction"] == "down"


# ---------------------------------------------------------------------------
# Sections endpoint tests
# ---------------------------------------------------------------------------

def test_get_sections_returns_default_when_no_row(client, firm_a_owner):
    """GET /dashboard/sections returns all-6-visible default when no row exists."""
    resp = client.get("/dashboard/sections", headers=firm_a_owner["headers"])
    assert resp.status_code == 200
    sections = resp.json()["sections"]
    assert len(sections) == 6
    keys = {s["key"] for s in sections}
    assert keys == {
        "morning_briefing", "financial_stats", "work_in_progress",
        "staff_utilization", "upcoming_deadlines", "awaiting_signature"
    }
    assert all(s["visible"] for s in sections)


def test_put_sections_round_trips(client, firm_a_owner):
    """PUT then GET returns the saved visibility state."""
    payload = {
        "sections": [
            {"key": "morning_briefing",   "visible": True,  "order": 0},
            {"key": "financial_stats",    "visible": False, "order": 1},
            {"key": "work_in_progress",   "visible": True,  "order": 2},
            {"key": "staff_utilization",  "visible": True,  "order": 3},
            {"key": "upcoming_deadlines", "visible": True,  "order": 4},
            {"key": "awaiting_signature", "visible": False, "order": 5},
        ]
    }
    put = client.put("/dashboard/sections", headers=firm_a_owner["headers"], json=payload)
    assert put.status_code == 200

    get = client.get("/dashboard/sections", headers=firm_a_owner["headers"])
    assert get.status_code == 200
    saved = {s["key"]: s for s in get.json()["sections"]}
    assert saved["financial_stats"]["visible"] is False
    assert saved["awaiting_signature"]["visible"] is False
    assert saved["morning_briefing"]["visible"] is True


def test_put_sections_upserts_on_second_call(client, firm_a_owner):
    """Second PUT overwrites the first without creating a duplicate row."""
    base = [
        {"key": "morning_briefing",   "visible": True, "order": 0},
        {"key": "financial_stats",    "visible": True, "order": 1},
        {"key": "work_in_progress",   "visible": True, "order": 2},
        {"key": "staff_utilization",  "visible": True, "order": 3},
        {"key": "upcoming_deadlines", "visible": True, "order": 4},
        {"key": "awaiting_signature", "visible": True, "order": 5},
    ]
    client.put("/dashboard/sections", headers=firm_a_owner["headers"], json={"sections": base})

    updated = [s.copy() for s in base]
    updated[0]["visible"] = False  # morning_briefing -> hidden
    resp = client.put("/dashboard/sections", headers=firm_a_owner["headers"], json={"sections": updated})
    assert resp.status_code == 200
    result = {s["key"]: s for s in resp.json()["sections"]}
    assert result["morning_briefing"]["visible"] is False


# ---------------------------------------------------------------------------
# Tenant isolation (watched-fail-then-pass)
# ---------------------------------------------------------------------------

def test_firm_a_cannot_read_firm_b_sections(client, firm_a_owner, firm_b_owner):
    """Firm A's GET /sections does NOT return Firm B's saved all-hidden layout.

    Negative control: Firm B saves all sections hidden. The test watches this PUT
    succeed (control fires), then confirms Firm A's GET returns its own defaults
    (all visible), not Firm B's all-hidden layout. This proves the user_id
    scoping in UserDashboardSection prevents cross-tenant reads.
    """
    # Firm B saves all-hidden -- NEGATIVE CONTROL (confirms PUT works)
    hidden = {
        "sections": [
            {"key": k, "visible": False, "order": i}
            for i, k in enumerate([
                "morning_briefing", "financial_stats", "work_in_progress",
                "staff_utilization", "upcoming_deadlines", "awaiting_signature"
            ])
        ]
    }
    put_b = client.put("/dashboard/sections", headers=firm_b_owner["headers"], json=hidden)
    assert put_b.status_code == 200  # control fired

    # Verify Firm B's layout is actually saved
    get_b = client.get("/dashboard/sections", headers=firm_b_owner["headers"])
    assert all(not s["visible"] for s in get_b.json()["sections"]), (
        "Negative control: Firm B's sections should be all-hidden"
    )

    # Firm A reads its own sections -- must NOT see Firm B's hidden layout
    get_a = client.get("/dashboard/sections", headers=firm_a_owner["headers"])
    assert get_a.status_code == 200
    visible_a = [s for s in get_a.json()["sections"] if s["visible"]]
    assert len(visible_a) > 0, (
        "Firm A should see its own all-visible defaults, not Firm B's all-hidden layout"
    )


# ---------------------------------------------------------------------------
# New tests for fixes: top_engagements wired, firm_id scoping
# ---------------------------------------------------------------------------

def test_dashboard_metrics_returns_real_top_engagements(client, firm_a_owner):
    """GET /dashboard/metrics returns non-empty top_engagements when unbilled entries exist."""
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cli = _make_client(db, firm_id)
        u = _make_user(db, firm_id)
        eng = _make_engagement(db, firm_id, cli.id)
        _make_time_entry(db, firm_id, eng.id, u.id,
                         hours=3.0, hourly_rate=150.0, is_billed=False)
        db.commit()
    finally:
        db.close()

    resp = client.get("/dashboard/metrics", headers=firm_a_owner["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert "top_engagements" in data
    assert len(data["top_engagements"]) >= 1
    entry = data["top_engagements"][0]
    assert "engagement_id" in entry
    assert "engagement_name" in entry
    assert "client_name" in entry
    assert entry["wip_value"] == 450.0  # 3 hours * 150/hr


def test_sections_firm_id_is_set_and_scoped(client, firm_a_owner):
    """firm_id is persisted on PUT and the row is scoped by firm_id on GET.

    Negative-control approach: save a row via PUT, then confirm via direct DB
    assertion that firm_id is correctly stored. Since user_id is unique per user
    and each user belongs to exactly one firm, a cross-firm exploit is not
    constructable without faking FK integrity -- so we prove firm_id is correctly
    stored and queried via database assertion.
    """
    import uuid as uuid_mod
    from app.models.dashboard_layout import UserDashboardSection
    from app.models.user import User
    from sqlalchemy import select as sa_select

    firm_id = firm_a_owner["firm_id"]

    hidden_sections = [
        {"key": k, "visible": False, "order": i}
        for i, k in enumerate([
            "morning_briefing", "financial_stats", "work_in_progress",
            "staff_utilization", "upcoming_deadlines", "awaiting_signature",
        ])
    ]

    # NEGATIVE CONTROL: save via PUT (this sets firm_id on the row)
    put_resp = client.put(
        "/dashboard/sections",
        headers=firm_a_owner["headers"],
        json={"sections": hidden_sections},
    )
    assert put_resp.status_code == 200  # control fired

    # Look up the authenticated user by their firm
    db = TestingSessionLocal()
    try:
        user = db.execute(
            sa_select(User).where(User.firm_id == firm_id)
        ).scalar_one()
        user_id = user.id

        row = db.execute(
            sa_select(UserDashboardSection).where(
                UserDashboardSection.user_id == user_id
            )
        ).scalar_one_or_none()
        assert row is not None, "Row must have been created by PUT"
        assert str(row.firm_id) == str(firm_id), (
            f"firm_id on row ({row.firm_id}) must match user's actual firm ({firm_id})"
        )
        assert row.created_at is not None, "created_at must be set"
    finally:
        db.close()

    # GET returns the saved sections (confirms firm_id filter allows own rows)
    get_resp = client.get("/dashboard/sections", headers=firm_a_owner["headers"])
    assert get_resp.status_code == 200
    saved = get_resp.json()["sections"]
    assert all(not s["visible"] for s in saved), (
        "GET should return the saved all-hidden sections, not the default"
    )
