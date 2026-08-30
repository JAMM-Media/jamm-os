# tests/test_portal_billing_detail.py
"""
Tests for GET /portal/billing-detail -- the engagement-level billing detail endpoint.

Response shape:
  {
    "groups": [
      {
        "engagement_key": str,
        "engagement_id": str | null,
        "engagement_name": str,
        "combined_subtotal": float,
        "combined_hours": float,
        "invoices": [
          {
            "invoice_id": str,
            "billed_on": str | null,
            "subtotal": float,
            "aggregate_hours": float,
            "line_items": [{"name": str, "description": str, "amount": float}]
          }
        ]
      }
    ],
    "total_billed_this_year": float,
    "average_per_engagement": float,
    "total_hours_this_year": float,
    "distinct_engagement_count": int,
    "engagements_this_year_count": int,
  }
"""

import uuid
from datetime import date, datetime, timezone

from app.core.enums import InvoiceDeliveryMethod, InvoiceStatus
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.firm import Firm
from app.models.invoice import Invoice
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.services.portal_auth import hash_portal_password
from tests.conftest import TestingSessionLocal


def _make_portal_client(firm_id: str, email: str = None) -> dict:
    email = email or f"billing-{uuid.uuid4().hex[:8]}@example.com"
    password = "Testpass1!"
    db = TestingSessionLocal()
    try:
        c = Client(
            firm_id=uuid.UUID(firm_id),
            name="Billing Test Client",
            email=email,
            portal_access_enabled=True,
            portal_password_hash=hash_portal_password(password),
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        return {"client_id": str(c.id), "email": email, "password": password}
    finally:
        db.close()


def _portal_login(http_client, firm_id: str, email: str, password: str) -> dict:
    db = TestingSessionLocal()
    try:
        firm = db.get(Firm, uuid.UUID(firm_id))
        slug = firm.slug
    finally:
        db.close()
    r = http_client.post("/portal/auth/login", json={
        "firm_slug": slug,
        "email": email,
        "password": password,
    })
    assert r.status_code == 200, f"Portal login failed: {r.json()}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_engagement(firm_id: str, client_id: str, name: str) -> str:
    db = TestingSessionLocal()
    try:
        e = Engagement(
            firm_id=uuid.UUID(firm_id),
            client_id=uuid.UUID(client_id),
            name=name,
            status="active",
        )
        db.add(e)
        db.commit()
        db.refresh(e)
        return str(e.id)
    finally:
        db.close()


def _make_invoice(firm_id: str, client_id: str, engagement_id: str = None,
                  status: InvoiceStatus = InvoiceStatus.sent,
                  total_amount: float = 1000.0,
                  line_items: list = None,
                  sent_at: datetime = None) -> str:
    db = TestingSessionLocal()
    try:
        inv = Invoice(
            firm_id=uuid.UUID(firm_id),
            client_id=uuid.UUID(client_id),
            engagement_id=uuid.UUID(engagement_id) if engagement_id else None,
            invoice_number=f"INV-{uuid.uuid4().hex[:6].upper()}",
            line_items=line_items or [
                {"description": "Service fee", "quantity": 1, "unit_price": total_amount, "total": total_amount}
            ],
            subtotal=total_amount,
            tax_rate=0.0,
            tax_amount=0.0,
            total_amount=total_amount,
            status=status,
            delivery_method=InvoiceDeliveryMethod.portal,
            is_deleted=False,
            sent_at=sent_at,
        )
        db.add(inv)
        db.commit()
        db.refresh(inv)
        return str(inv.id)
    finally:
        db.close()


def _make_time_entry(firm_id: str, engagement_id: str, invoice_id: str,
                     hours: float, user_id: str) -> str:
    db = TestingSessionLocal()
    try:
        te = TimeEntry(
            firm_id=uuid.UUID(firm_id),
            engagement_id=uuid.UUID(engagement_id),
            invoice_id=uuid.UUID(invoice_id),
            user_id=uuid.UUID(user_id),
            description="Billable work",
            hours=hours,
            hourly_rate=100.0,
            is_billable=True,
            is_billed=True,
            date=date.today(),
        )
        db.add(te)
        db.commit()
        db.refresh(te)
        return str(te.id)
    finally:
        db.close()


def _get_any_user_id(firm_id: str) -> str:
    db = TestingSessionLocal()
    try:
        user = db.execute(
            __import__("sqlalchemy").select(User).where(User.firm_id == uuid.UUID(firm_id))
        ).scalars().first()
        if user:
            return str(user.id)
        return None
    finally:
        db.close()


def test_client_retrieves_own_billing_detail(client, firm_a_owner):
    """
    Authenticated client can fetch their own billing detail.
    Response groups invoices by engagement. Check combined_subtotal and
    that the invoice's line items are accessible inside the group.
    """
    firm_id = firm_a_owner["firm_id"]
    portal = _make_portal_client(firm_id)
    headers = _portal_login(client, firm_id, portal["email"], portal["password"])

    eng_id = _make_engagement(firm_id, portal["client_id"], "Q3 Bookkeeping")
    inv_id = _make_invoice(
        firm_id, portal["client_id"], eng_id,
        total_amount=1250.0,
        line_items=[
            {"description": "Monthly Bookkeeping", "quantity": 1, "unit_price": 1200.0, "total": 1200.0},
            {"description": "Bank Reconciliation", "quantity": 1, "unit_price": 50.0, "total": 50.0},
        ]
    )

    user_id = _get_any_user_id(firm_id)
    if user_id:
        _make_time_entry(firm_id, eng_id, inv_id, hours=5.5, user_id=user_id)
        _make_time_entry(firm_id, eng_id, inv_id, hours=3.0, user_id=user_id)

    r = client.get("/portal/billing-detail", headers=headers)
    assert r.status_code == 200, r.json()

    data = r.json()
    assert "groups" in data
    assert "total_billed_this_year" in data
    assert "average_per_engagement" in data
    assert "total_hours_this_year" in data

    groups = data["groups"]
    assert len(groups) >= 1

    our_group = next((g for g in groups if g["engagement_name"] == "Q3 Bookkeeping"), None)
    assert our_group is not None, f"Q3 Bookkeeping group not found in: {[g['engagement_name'] for g in groups]}"
    assert our_group["combined_subtotal"] == 1250.0
    assert len(our_group["invoices"]) == 1

    inv_entry = our_group["invoices"][0]
    assert inv_entry["invoice_id"] == inv_id
    assert inv_entry["subtotal"] == 1250.0
    assert len(inv_entry["line_items"]) == 2

    descriptions = [item["description"] for item in inv_entry["line_items"]]
    assert "Monthly Bookkeeping" in descriptions
    assert "Bank Reconciliation" in descriptions

    if user_id:
        assert inv_entry["aggregate_hours"] == 8.5, (
            f"Expected 8.5 aggregate hours (5.5+3.0), got {inv_entry['aggregate_hours']}"
        )


def test_client_cannot_retrieve_another_clients_billing_detail(client, firm_a_owner):
    """
    Tenant isolation: client B's engagement must not appear in client A's billing detail.
    """
    firm_id = firm_a_owner["firm_id"]
    client_a = _make_portal_client(firm_id)
    client_b = _make_portal_client(firm_id)

    eng_id = _make_engagement(firm_id, client_b["client_id"], "Client B Engagement")
    _make_invoice(firm_id, client_b["client_id"], eng_id, total_amount=999.0)

    headers_a = _portal_login(client, firm_id, client_a["email"], client_a["password"])
    r = client.get("/portal/billing-detail", headers=headers_a)
    assert r.status_code == 200, r.json()

    groups = r.json()["groups"]
    b_found = any(g["engagement_name"] == "Client B Engagement" for g in groups)
    assert not b_found, "Client A should not see client B's engagement"


def test_invoice_with_no_time_entries_returns_zero_hours(client, firm_a_owner):
    """
    An invoice with no linked time entries must return aggregate_hours = 0.0
    on the nested invoice entry. Zero must be present, not omitted.
    """
    firm_id = firm_a_owner["firm_id"]
    portal = _make_portal_client(firm_id)
    headers = _portal_login(client, firm_id, portal["email"], portal["password"])

    eng_id = _make_engagement(firm_id, portal["client_id"], "No-Hours Engagement")
    inv_id = _make_invoice(firm_id, portal["client_id"], eng_id, total_amount=500.0)

    r = client.get("/portal/billing-detail", headers=headers)
    assert r.status_code == 200, r.json()

    groups = r.json()["groups"]
    our_group = next((g for g in groups if g["engagement_name"] == "No-Hours Engagement"), None)
    assert our_group is not None
    assert len(our_group["invoices"]) == 1

    inv_entry = our_group["invoices"][0]
    assert inv_entry["invoice_id"] == inv_id
    assert inv_entry["aggregate_hours"] == 0.0, (
        f"Expected 0.0 hours for invoice with no time entries, got {inv_entry['aggregate_hours']}"
    )


def test_endpoint_returns_new_format_not_old_billing_report_list(client, firm_a_owner):
    """
    The endpoint must return the engagement-grouped dict format, not the old
    flat BillingDetailReport list.
    """
    firm_id = firm_a_owner["firm_id"]
    portal = _make_portal_client(firm_id)
    headers = _portal_login(client, firm_id, portal["email"], portal["password"])

    r = client.get("/portal/billing-detail", headers=headers)
    assert r.status_code == 200, r.json()

    data = r.json()
    assert isinstance(data, dict), f"Expected dict, got {type(data)}"
    assert "groups" in data
    assert "total_billed_this_year" in data
    assert "average_per_engagement" in data
    assert "total_hours_this_year" in data
    assert "id" not in data, "Old BillingDetailReport 'id' must not appear"


def test_engagement_with_two_invoices_produces_one_group(client, firm_a_owner):
    """
    An engagement with 2 invoices must produce exactly 1 group (not 2),
    with combined_subtotal equal to the sum of both invoice amounts, and
    both invoices present in the group's invoices array.
    """
    firm_id = firm_a_owner["firm_id"]
    portal = _make_portal_client(firm_id)
    headers = _portal_login(client, firm_id, portal["email"], portal["password"])

    eng_id = _make_engagement(firm_id, portal["client_id"], "Quarterly Bookkeeping")
    inv1 = _make_invoice(
        firm_id, portal["client_id"], eng_id, total_amount=500.0,
        sent_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    inv2 = _make_invoice(
        firm_id, portal["client_id"], eng_id, total_amount=600.0,
        sent_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )

    r = client.get("/portal/billing-detail", headers=headers)
    assert r.status_code == 200, r.json()

    data = r.json()
    groups = data["groups"]
    our_groups = [g for g in groups if g["engagement_name"] == "Quarterly Bookkeeping"]

    assert len(our_groups) == 1, (
        f"Expected 1 engagement group for 'Quarterly Bookkeeping', got {len(our_groups)}"
    )
    grp = our_groups[0]
    assert grp["combined_subtotal"] == 1100.0, (
        f"Expected combined_subtotal=1100.0 (500+600), got {grp['combined_subtotal']}"
    )
    assert len(grp["invoices"]) == 2, (
        f"Expected 2 invoices inside the group, got {len(grp['invoices'])}"
    )

    invoice_ids_in_group = {inv["invoice_id"] for inv in grp["invoices"]}
    assert inv1 in invoice_ids_in_group, f"Invoice {inv1} missing from group invoices"
    assert inv2 in invoice_ids_in_group, f"Invoice {inv2} missing from group invoices"

    # Invoices sorted billed_on descending: May before March
    assert grp["invoices"][0]["invoice_id"] == inv2, (
        "Expected more recent invoice (May 2026) first"
    )
    assert grp["invoices"][1]["invoice_id"] == inv1, (
        "Expected older invoice (March 2026) second"
    )


def test_single_invoice_engagement_still_works(client, firm_a_owner):
    """
    Regression: an engagement with exactly 1 invoice still produces a valid
    group with 1 invoice nested inside, and combined_subtotal equals that
    invoice's subtotal.
    """
    firm_id = firm_a_owner["firm_id"]
    portal = _make_portal_client(firm_id)
    headers = _portal_login(client, firm_id, portal["email"], portal["password"])

    eng_id = _make_engagement(firm_id, portal["client_id"], "Single Invoice Engagement")
    inv_id = _make_invoice(firm_id, portal["client_id"], eng_id, total_amount=750.0)

    r = client.get("/portal/billing-detail", headers=headers)
    assert r.status_code == 200, r.json()

    data = r.json()
    our_group = next(
        (g for g in data["groups"] if g["engagement_name"] == "Single Invoice Engagement"),
        None,
    )
    assert our_group is not None
    assert our_group["combined_subtotal"] == 750.0
    assert len(our_group["invoices"]) == 1
    assert our_group["invoices"][0]["invoice_id"] == inv_id


def test_orphan_invoice_counts_as_own_distinct_entity(client, firm_a_owner):
    """
    An invoice with no engagement_id is its own group. Two orphan invoices
    produce 2 groups, each with 1 invoice.
    """
    firm_id = firm_a_owner["firm_id"]
    portal = _make_portal_client(firm_id)
    headers = _portal_login(client, firm_id, portal["email"], portal["password"])

    _make_invoice(firm_id, portal["client_id"], engagement_id=None, total_amount=300.0)
    _make_invoice(firm_id, portal["client_id"], engagement_id=None, total_amount=400.0)

    r = client.get("/portal/billing-detail", headers=headers)
    assert r.status_code == 200, r.json()

    data = r.json()
    orphan_groups = [g for g in data["groups"] if g["engagement_id"] is None]
    assert len(orphan_groups) >= 2, (
        f"Expected at least 2 orphan groups, got {len(orphan_groups)}"
    )
    assert data["distinct_engagement_count"] >= 2, (
        f"Expected distinct_engagement_count >= 2, got {data['distinct_engagement_count']}"
    )


def test_one_engagement_this_year_returns_count_of_one(client, firm_a_owner):
    """
    A client with exactly 1 engagement with current-year activity must receive
    engagements_this_year_count == 1. The frontend uses this to suppress the
    Average per engagement card (meaningless when it equals Total billed).
    """
    firm_id = firm_a_owner["firm_id"]
    portal = _make_portal_client(firm_id)
    headers = _portal_login(client, firm_id, portal["email"], portal["password"])

    eng_id = _make_engagement(firm_id, portal["client_id"], "Current Year Only Engagement")
    _make_invoice(
        firm_id, portal["client_id"], eng_id,
        total_amount=1500.0,
        status=InvoiceStatus.sent,
    )

    r = client.get("/portal/billing-detail", headers=headers)
    assert r.status_code == 200, r.json()

    data = r.json()
    assert "engagements_this_year_count" in data, (
        f"Response missing 'engagements_this_year_count'. Keys: {list(data.keys())}"
    )
    assert data["engagements_this_year_count"] == 1, (
        f"Expected engagements_this_year_count=1, got {data['engagements_this_year_count']}"
    )