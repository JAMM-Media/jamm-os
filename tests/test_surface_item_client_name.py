# tests/test_surface_item_client_name.py
"""
Guard tests for client_name enrichment on surface item API responses.

Tests:
  a. get_briefing() returns the correct client_name for a row whose payload
     carries a valid client_id belonging to the requesting firm.
  b. A row whose payload has no client_id key returns client_name: None
     without raising.
  c. Firm B's client name never appears in Firm A's briefing response --
     real tenant isolation enforced at the read-time query.
"""

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from app.core.enums import InvoiceStatus, SurfaceKind
from app.models.client import Client
from app.models.invoice import Invoice
from app.models.surface_item import SurfaceItem
from app.services.surface_daily_job import run_surface_generation_for_firm
from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(firm_id, name):
    db = TestingSessionLocal()
    try:
        c = Client(
            firm_id=firm_id,
            name=name,
            email=f"{uuid4().hex[:8]}@example.com",
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        return c.id
    finally:
        db.close()


def _make_overdue_invoice(firm_id, client_id):
    db = TestingSessionLocal()
    try:
        inv = Invoice(
            firm_id=firm_id,
            client_id=client_id,
            invoice_number=f"INV-{uuid4().hex[:8]}",
            subtotal=Decimal("500.00"),
            total_amount=Decimal("500.00"),
            amount_paid=Decimal("0.00"),
            status=InvoiceStatus.sent,
            due_date=date.today() - timedelta(days=10),
        )
        db.add(inv)
        db.commit()
    finally:
        db.close()


def _seed_bare_briefing_row(firm_id):
    """Insert a briefing row whose payload has no client_id key."""
    db = TestingSessionLocal()
    try:
        row = SurfaceItem(
            firm_id=firm_id,
            kind=SurfaceKind.briefing,
            item_type="no_client_id_type",
            dedup_key=f"bare-{uuid4().hex[:8]}",
            headline="No client ID in this payload",
            payload={},
            rank=0,
            slotted_at=__import__('datetime').datetime.now(
                __import__('datetime').timezone.utc
            ),
        )
        db.add(row)
        db.commit()
    finally:
        db.close()


def _run_job(firm_id):
    db = TestingSessionLocal()
    try:
        run_surface_generation_for_firm(db, firm_id)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test (a): correct client_name returned for a valid client_id
# ---------------------------------------------------------------------------

def test_briefing_returns_correct_client_name(client, firm_a_owner):
    """A briefing row backed by a real client carries its name in the response."""
    firm_id = firm_a_owner["firm_id"]
    headers = firm_a_owner["headers"]

    client_id = _make_client(firm_id, "Riverside Accounting")
    _make_overdue_invoice(firm_id, client_id)
    _run_job(firm_id)

    resp = client.get("/api/v1/briefing", headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    items = resp.json()["items"]

    overdue_items = [i for i in items if i["item_type"] == "invoice_overdue"]
    assert overdue_items, "Expected at least one invoice_overdue item in briefing"

    item = overdue_items[0]
    assert item["client_name"] == "Riverside Accounting", (
        f"Expected 'Riverside Accounting', got {item['client_name']!r}"
    )


# ---------------------------------------------------------------------------
# Test (b): no client_id in payload -> client_name is None, no error
# ---------------------------------------------------------------------------

def test_briefing_row_without_client_id_returns_none(client, firm_a_owner):
    """A row with no client_id in its payload returns client_name: None without raising."""
    firm_id = firm_a_owner["firm_id"]
    headers = firm_a_owner["headers"]

    _seed_bare_briefing_row(firm_id)

    resp = client.get("/api/v1/briefing", headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    items = resp.json()["items"]

    bare_items = [i for i in items if i["item_type"] == "no_client_id_type"]
    assert bare_items, "Expected the bare row to appear in briefing"

    assert bare_items[0]["client_name"] is None, (
        f"Expected None for row with no client_id, got {bare_items[0]['client_name']!r}"
    )


# ---------------------------------------------------------------------------
# Test (c): tenant isolation -- Firm B's client name never leaks into Firm A
# ---------------------------------------------------------------------------

def test_briefing_client_name_never_leaks_across_firms(client, firm_a_owner, firm_b_owner):
    """Firm B's client is not returned for Firm A's briefing rows."""
    firm_a_id = firm_a_owner["firm_id"]
    firm_b_id = firm_b_owner["firm_id"]
    headers_a = firm_a_owner["headers"]

    # Create a client in Firm B with a distinctive name.
    firm_b_client_id = _make_client(firm_b_id, "Should Never Appear In Firm A")

    # Inject a Firm A briefing row whose payload points at Firm B's client_id.
    db = TestingSessionLocal()
    try:
        row = SurfaceItem(
            firm_id=firm_a_id,
            kind=SurfaceKind.briefing,
            item_type="cross_firm_probe",
            dedup_key=f"probe-{uuid4().hex[:8]}",
            headline="Cross-firm probe row",
            payload={"client_id": str(firm_b_client_id)},
            rank=0,
            slotted_at=__import__('datetime').datetime.now(
                __import__('datetime').timezone.utc
            ),
        )
        db.add(row)
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/v1/briefing", headers=headers_a)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    items = resp.json()["items"]

    probe_items = [i for i in items if i["item_type"] == "cross_firm_probe"]
    assert probe_items, "Expected the probe row to appear in Firm A's briefing"

    assert probe_items[0]["client_name"] is None, (
        "Firm B's client name must never appear in Firm A's response; "
        f"got {probe_items[0]['client_name']!r}"
    )
    for item in items:
        assert item["client_name"] != "Should Never Appear In Firm A", (
            "Firm B client name leaked into Firm A response"
        )
