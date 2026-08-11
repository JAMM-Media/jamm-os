# tests/test_phase7_billing.py

"""
Phase 7 — Billing & Payments test suite.

Tests cover: invoice CRUD, invoice lifecycle, time entry CRUD,
webhook handling, tenant isolation, and portal billing.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from tests.conftest import TestingSessionLocal
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.firm import Firm
from app.models.invoice import Invoice
from app.models.stripe_connection import StripeConnection
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.core.security import get_password_hash
from app.core.enums import InvoiceStatus, UserRole
from app.services.portal_auth import hash_portal_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm_and_staff(slug="billing-firm", staff_email="billing_staff@firm.com"):
    """Insert a Firm + firm_owner user. Returns (firm_id, firm_slug, user_id)."""
    db = TestingSessionLocal()
    try:
        firm = Firm(name="Billing Test Firm", slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)

        user = User(
            firm_id=firm.id,
            email=staff_email,
            hashed_password=get_password_hash("staffpass"),
            full_name="Billing Staff",
            role=UserRole.firm_owner,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        firm_id = firm.id
        firm_slug = firm.slug
        user_id = user.id
    finally:
        db.close()
    return firm_id, firm_slug, user_id


def _make_portal_client(firm_id, email="portal_client@example.com", password="Password1!"):
    """Insert a Client with portal access enabled. Returns client_id."""
    db = TestingSessionLocal()
    try:
        c = Client(
            firm_id=firm_id,
            name="Portal Billing Client",
            email=email,
            portal_password_hash=hash_portal_password(password),
            portal_access_enabled=True,
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        client_id = c.id
    finally:
        db.close()
    return client_id


def _create_client_in_db(firm_id):
    """Insert a plain Client (no portal access). Returns client_id."""
    db = TestingSessionLocal()
    try:
        c = Client(
            firm_id=firm_id,
            name="Test Client",
            email=f"client_{uuid.uuid4().hex[:8]}@test.com",
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        client_id = c.id
    finally:
        db.close()
    return client_id


def _create_invoice_in_db(
    firm_id,
    client_id,
    total_amount="1000.00",
    status=InvoiceStatus.sent,
    sent_at=None,
    paid_at=None,
    stripe_payment_intent_id="pi_test_webhook",
):
    """Insert an Invoice directly (bypasses POST /invoices/). Returns invoice_id."""
    db = TestingSessionLocal()
    try:
        inv = Invoice(
            firm_id=firm_id,
            client_id=client_id,
            invoice_number=f"INV-{uuid.uuid4().hex[:8]}",
            subtotal=Decimal(total_amount),
            tax_rate=Decimal("0.0"),
            tax_amount=Decimal("0.0"),
            total_amount=Decimal(total_amount),
            status=status,
            sent_at=sent_at or datetime.now(timezone.utc),
            paid_at=paid_at,
            stripe_payment_intent_id=stripe_payment_intent_id,
        )
        db.add(inv)
        db.commit()
        db.refresh(inv)
        invoice_id = inv.id
    finally:
        db.close()
    return invoice_id


def _create_engagement_in_db(firm_id, client_id):
    """Insert an Engagement. Returns engagement_id."""
    db = TestingSessionLocal()
    try:
        eng = Engagement(
            firm_id=firm_id,
            client_id=client_id,
            name="Test Engagement",
            status="active",
        )
        db.add(eng)
        db.commit()
        db.refresh(eng)
        engagement_id = eng.id
    finally:
        db.close()
    return engagement_id


def _staff_login(http_client, email, password="staffpass"):
    r = http_client.post("/auth/token", json={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _portal_login(http_client, firm_slug, email, password="Password1!"):
    return http_client.post("/portal/auth/login", json={
        "email": email,
        "firm_slug": firm_slug,
        "password": password,
    })


def _portal_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _invoice_payload(client_id):
    """Build a valid InvoiceCreate payload. invoice_number is overridden by CRUD."""
    return {
        "invoice_number": "",
        "client_id": str(client_id),
        "line_items": [
            {
                "description": "Tax Preparation",
                "quantity": "1",
                "unit_price": "500.00",
                "total": "500.00",
            }
        ],
        "subtotal": "500.00",
        "tax_rate": "0.0",
        "tax_amount": "0.0",
        "total_amount": "500.00",
    }


_WEBHOOK_MOCK = "app.services.stripe_service.stripe.Webhook.construct_event"


# ===========================================================================
# GROUP 1 — Invoice CRUD
# ===========================================================================

def test_create_invoice(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)

    r = client.post("/invoices/", json=_invoice_payload(client_id), headers=headers)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["invoice_number"].startswith("INV-")
    assert data["status"] == "draft"
    assert Decimal(str(data["total_amount"])) == Decimal("500.00")


def test_invoice_number_sequential(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)

    r1 = client.post("/invoices/", json=_invoice_payload(client_id), headers=headers)
    r2 = client.post("/invoices/", json=_invoice_payload(client_id), headers=headers)
    assert r1.status_code == 201 and r2.status_code == 201

    num1 = int(r1.json()["invoice_number"].split("-")[1])
    num2 = int(r2.json()["invoice_number"].split("-")[1])
    assert num2 == num1 + 1


def test_get_invoice(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)

    created = client.post("/invoices/", json=_invoice_payload(client_id), headers=headers).json()
    invoice_id = created["id"]

    r = client.get(f"/invoices/{invoice_id}", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["invoice_number"] == created["invoice_number"]


def test_list_invoices(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)

    client.post("/invoices/", json=_invoice_payload(client_id), headers=headers)
    client.post("/invoices/", json=_invoice_payload(client_id), headers=headers)

    r = client.get("/invoices/", headers=headers)
    assert r.status_code == 200, r.text
    assert len(r.json()["items"]) >= 2


def test_update_invoice(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)

    invoice_id = client.post("/invoices/", json=_invoice_payload(client_id), headers=headers).json()["id"]

    r = client.patch(
        f"/invoices/{invoice_id}",
        json={"notes_client_visible": "Thank you for your business"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["notes_client_visible"] == "Thank you for your business"


def test_cannot_update_paid_invoice(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)

    invoice_id = client.post("/invoices/", json=_invoice_payload(client_id), headers=headers).json()["id"]

    db = TestingSessionLocal()
    try:
        inv = db.get(Invoice, uuid.UUID(invoice_id))
        inv.status = InvoiceStatus.paid
        db.commit()
    finally:
        db.close()

    r = client.patch(
        f"/invoices/{invoice_id}",
        json={"notes_client_visible": "updated"},
        headers=headers,
    )
    assert r.status_code == 400, r.text


def test_soft_delete_invoice(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)

    invoice_id = client.post("/invoices/", json=_invoice_payload(client_id), headers=headers).json()["id"]

    r = client.delete(f"/invoices/{invoice_id}", headers=headers)
    assert r.status_code == 200, r.text

    r2 = client.get(f"/invoices/{invoice_id}", headers=headers)
    assert r2.status_code == 404, r2.text


def test_cannot_delete_paid_invoice(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)

    invoice_id = client.post("/invoices/", json=_invoice_payload(client_id), headers=headers).json()["id"]

    db = TestingSessionLocal()
    try:
        inv = db.get(Invoice, uuid.UUID(invoice_id))
        inv.status = InvoiceStatus.paid
        db.commit()
    finally:
        db.close()

    r = client.delete(f"/invoices/{invoice_id}", headers=headers)
    assert r.status_code == 400, r.text


def test_cannot_delete_paid_invoice_detail_message(client, firm_a_owner):
    """
    Pins the exact client-visible refusal. The guard moved from the router into
    invoice_service, and this is what proves the move changed no behavior.
    """
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)

    invoice_id = client.post("/invoices/", json=_invoice_payload(client_id), headers=headers).json()["id"]

    db = TestingSessionLocal()
    try:
        inv = db.get(Invoice, uuid.UUID(invoice_id))
        inv.status = InvoiceStatus.paid
        db.commit()
    finally:
        db.close()

    r = client.delete(f"/invoices/{invoice_id}", headers=headers)
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Cannot delete a paid invoice"

    missing = client.delete(f"/invoices/{uuid.uuid4()}", headers=headers)
    assert missing.status_code == 404, missing.text
    assert missing.json()["detail"] == "Invoice not found"


# ===========================================================================
# GROUP 2 — Invoice lifecycle
# ===========================================================================

def test_send_invoice(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)

    payload = {**_invoice_payload(client_id), "due_date": date(2026, 8, 1).isoformat()}
    invoice_id = client.post("/invoices/", json=payload, headers=headers).json()["id"]

    r = client.post(f"/invoices/{invoice_id}/send", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "sent"
    assert data["sent_at"] is not None


def test_first_invoice_sent_fires_exactly_once(client, firm_a_owner):
    """
    firm.first_invoice_sent must fire on the firm's first-ever sent invoice
    and never again, even after that invoice's status later changes away
    from 'sent' (e.g. to paid) and a second invoice is sent.
    """
    from app.models.behavioral_event import BehavioralEvent
    from sqlalchemy import select as sa_select

    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)

    payload_a = {**_invoice_payload(client_id), "due_date": date(2026, 8, 1).isoformat()}
    invoice_a_id = client.post("/invoices/", json=payload_a, headers=headers).json()["id"]
    send_a = client.post(f"/invoices/{invoice_a_id}/send", headers=headers)
    assert send_a.status_code == 200, send_a.text

    db = TestingSessionLocal()
    try:
        inv_a = db.get(Invoice, uuid.UUID(invoice_a_id))
        inv_a.status = InvoiceStatus.paid
        db.commit()
    finally:
        db.close()

    payload_b = {**_invoice_payload(client_id), "due_date": date(2026, 8, 15).isoformat()}
    invoice_b_id = client.post("/invoices/", json=payload_b, headers=headers).json()["id"]
    send_b = client.post(f"/invoices/{invoice_b_id}/send", headers=headers)
    assert send_b.status_code == 200, send_b.text

    db = TestingSessionLocal()
    try:
        rows = db.execute(
            sa_select(BehavioralEvent).where(
                BehavioralEvent.firm_id == firm_id,
                BehavioralEvent.event_type == "firm.first_invoice_sent",
            )
        ).scalars().all()
        assert len(rows) == 1, f"expected exactly 1 firm.first_invoice_sent event, got {len(rows)}"
    finally:
        db.close()


def test_cannot_send_invoice_without_due_date(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)

    invoice_id = client.post("/invoices/", json=_invoice_payload(client_id), headers=headers).json()["id"]

    r = client.post(f"/invoices/{invoice_id}/send", headers=headers)
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Invoice must have a due date before it can be sent"


def test_cannot_send_already_sent_invoice(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)

    payload = {**_invoice_payload(client_id), "due_date": date(2026, 8, 1).isoformat()}
    invoice_id = client.post("/invoices/", json=payload, headers=headers).json()["id"]
    first_send = client.post(f"/invoices/{invoice_id}/send", headers=headers)
    assert first_send.status_code == 200, first_send.text

    r = client.post(f"/invoices/{invoice_id}/send", headers=headers)
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Invoice already sent"


@pytest.mark.skip(reason="WeasyPrint requires GTK")
def test_invoice_pdf_endpoint(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)

    invoice_id = client.post("/invoices/", json=_invoice_payload(client_id), headers=headers).json()["id"]

    r = client.get(f"/invoices/{invoice_id}/pdf", headers=headers)
    assert r.status_code == 200
    assert "application/pdf" in r.headers["content-type"]
    assert len(r.content) > 0


def test_invoice_from_time_entries(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)
    engagement_id = _create_engagement_in_db(firm_id, client_id)
    today = date.today().isoformat()

    r1 = client.post(
        "/time-entries/",
        json={
            "engagement_id": str(engagement_id),
            "description": "Research",
            "hours": "2.0",
            "hourly_rate": "150.00",
            "is_billable": True,
            "date": today,
        },
        headers=headers,
    )
    assert r1.status_code == 201, r1.text
    entry1_id = r1.json()["id"]

    r2 = client.post(
        "/time-entries/",
        json={
            "engagement_id": str(engagement_id),
            "description": "Filing",
            "hours": "1.5",
            "hourly_rate": "150.00",
            "is_billable": True,
            "date": today,
        },
        headers=headers,
    )
    assert r2.status_code == 201, r2.text
    entry2_id = r2.json()["id"]

    r = client.post(
        "/invoices/from-time-entries",
        json={"engagement_id": str(engagement_id)},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert Decimal(str(data["total_amount"])) == Decimal("525.00")
    assert len(data["line_items"]) == 2

    # Verify both entries are now marked as billed
    re1 = client.get(f"/time-entries/{entry1_id}", headers=headers)
    re2 = client.get(f"/time-entries/{entry2_id}", headers=headers)
    assert re1.json()["is_billed"] is True
    assert re2.json()["is_billed"] is True


# ===========================================================================
# GROUP 3 — Time entry CRUD
# ===========================================================================

def test_create_time_entry(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)
    engagement_id = _create_engagement_in_db(firm_id, client_id)
    today = date.today().isoformat()

    r = client.post(
        "/time-entries/",
        json={
            "engagement_id": str(engagement_id),
            "description": "Client meeting",
            "hours": "2.0",
            "hourly_rate": "200.00",
            "is_billable": True,
            "date": today,
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert Decimal(str(data["hours"])) == Decimal("2.00")
    assert Decimal(str(data["hourly_rate"])) == Decimal("200.00")


def test_list_time_entries(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)
    engagement_id = _create_engagement_in_db(firm_id, client_id)
    today = date.today().isoformat()

    for desc in ("Entry A", "Entry B"):
        client.post(
            "/time-entries/",
            json={
                "engagement_id": str(engagement_id),
                "description": desc,
                "hours": "1.0",
                "hourly_rate": "100.00",
                "is_billable": True,
                "date": today,
            },
            headers=headers,
        )

    r = client.get("/time-entries/", headers=headers)
    assert r.status_code == 200, r.text
    assert len(r.json()["items"]) >= 2


def test_update_time_entry(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)
    engagement_id = _create_engagement_in_db(firm_id, client_id)
    today = date.today().isoformat()

    entry_id = client.post(
        "/time-entries/",
        json={
            "engagement_id": str(engagement_id),
            "description": "Initial entry",
            "hours": "1.0",
            "hourly_rate": "100.00",
            "is_billable": True,
            "date": today,
        },
        headers=headers,
    ).json()["id"]

    r = client.patch(f"/time-entries/{entry_id}", json={"hours": "3.0"}, headers=headers)
    assert r.status_code == 200, r.text
    assert Decimal(str(r.json()["hours"])) == Decimal("3.00")


def test_cannot_update_billed_entry(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)
    engagement_id = _create_engagement_in_db(firm_id, client_id)
    today = date.today().isoformat()

    entry_id = client.post(
        "/time-entries/",
        json={
            "engagement_id": str(engagement_id),
            "description": "Billed entry",
            "hours": "2.0",
            "hourly_rate": "100.00",
            "is_billable": True,
            "date": today,
        },
        headers=headers,
    ).json()["id"]

    db = TestingSessionLocal()
    try:
        entry = db.get(TimeEntry, uuid.UUID(entry_id))
        entry.is_billed = True
        db.commit()
    finally:
        db.close()

    r = client.patch(f"/time-entries/{entry_id}", json={"hours": "5.0"}, headers=headers)
    assert r.status_code == 400, r.text


def test_delete_time_entry(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)
    engagement_id = _create_engagement_in_db(firm_id, client_id)
    today = date.today().isoformat()

    entry_id = client.post(
        "/time-entries/",
        json={
            "engagement_id": str(engagement_id),
            "description": "To delete",
            "hours": "1.0",
            "hourly_rate": "50.00",
            "is_billable": False,
            "date": today,
        },
        headers=headers,
    ).json()["id"]

    r = client.delete(f"/time-entries/{entry_id}", headers=headers)
    assert r.status_code == 200, r.text

    r2 = client.get(f"/time-entries/{entry_id}", headers=headers)
    assert r2.status_code == 404, r2.text


def test_cannot_delete_billed_time_entry(client, firm_a_owner):
    """
    A billed entry has already been invoiced, so deleting it would silently
    detach revenue from its work record. The refusal was previously untested,
    which left the guard with no way to be observed failing.
    """
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)
    engagement_id = _create_engagement_in_db(firm_id, client_id)
    today = date.today().isoformat()

    entry_id = client.post(
        "/time-entries/",
        json={
            "engagement_id": str(engagement_id),
            "description": "Billed and undeletable",
            "hours": "2.0",
            "hourly_rate": "100.00",
            "is_billable": True,
            "date": today,
        },
        headers=headers,
    ).json()["id"]

    db = TestingSessionLocal()
    try:
        entry = db.get(TimeEntry, uuid.UUID(entry_id))
        entry.is_billed = True
        db.commit()
    finally:
        db.close()

    r = client.delete(f"/time-entries/{entry_id}", headers=headers)
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Cannot delete a billed time entry"

    # Reads the table directly: the delete endpoint's own filtering could hide
    # a row that is still there.
    db = TestingSessionLocal()
    try:
        assert db.get(TimeEntry, uuid.UUID(entry_id)) is not None
    finally:
        db.close()

    missing = client.delete(f"/time-entries/{uuid.uuid4()}", headers=headers)
    assert missing.status_code == 404, missing.text
    assert missing.json()["detail"] == "Time entry not found"


# ===========================================================================
# GROUP 4 — Webhook handler
# ===========================================================================

def test_webhook_payment_succeeded(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]
    client_id = _create_client_in_db(firm_id)

    invoice_id = client.post("/invoices/", json=_invoice_payload(client_id), headers=headers).json()["id"]

    db = TestingSessionLocal()
    try:
        inv = db.get(Invoice, uuid.UUID(invoice_id))
        inv.stripe_payment_intent_id = "pi_test_123"
        db.commit()
    finally:
        db.close()

    fake_event = {
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_test_123",
                "metadata": {"invoice_id": invoice_id},
                "latest_charge": "ch_test_456",
                "charges_enabled": True,
                "payouts_enabled": True,
                "details_submitted": True,
            }
        },
    }

    with patch(_WEBHOOK_MOCK, return_value=fake_event):
        r = client.post(
            "/payments/webhook",
            content=b'{"type":"payment_intent.succeeded"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    assert r.status_code == 200, r.text
    assert r.json() == {"status": "ok"}

    db = TestingSessionLocal()
    try:
        inv = db.get(Invoice, uuid.UUID(invoice_id))
        assert inv.status == InvoiceStatus.paid
        assert inv.stripe_charge_id == "ch_test_456"
    finally:
        db.close()


def test_webhook_invalid_signature(client):
    r = client.post(
        "/payments/webhook",
        content=b'{"type":"test"}',
        headers={"stripe-signature": "t=bad,v1=invalid"},
    )
    assert r.status_code == 400, r.text


def test_webhook_payment_failed(client):
    fake_event = {
        "type": "payment_intent.payment_failed",
        "data": {
            "object": {
                "id": "pi_test_failed",
                "metadata": {"invoice_id": str(uuid.uuid4())},
            }
        },
    }

    with patch(_WEBHOOK_MOCK, return_value=fake_event):
        r = client.post(
            "/payments/webhook",
            content=b'{"type":"payment_intent.payment_failed"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    assert r.status_code == 200, r.text
    assert r.json() == {"status": "ok"}


def test_webhook_account_updated(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])

    db = TestingSessionLocal()
    conn_id = None
    try:
        conn = StripeConnection(
            firm_id=firm_id,
            stripe_account_id="acct_test_999",
            charges_enabled=False,
            payouts_enabled=False,
            details_submitted=False,
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)
        conn_id = conn.id
        account_id = conn.stripe_account_id
    finally:
        db.close()

    fake_event = {
        "type": "account.updated",
        "data": {
            "object": {
                "id": account_id,
                "charges_enabled": True,
                "payouts_enabled": True,
                "details_submitted": True,
            }
        },
    }

    with patch(_WEBHOOK_MOCK, return_value=fake_event):
        r = client.post(
            "/payments/webhook",
            content=b'{"type":"account.updated"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    assert r.status_code == 200, r.text

    db = TestingSessionLocal()
    try:
        conn = db.get(StripeConnection, conn_id)
        assert conn.charges_enabled is True
    finally:
        db.close()


def test_webhook_partial_payment(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    client_id = _create_client_in_db(firm_id)
    invoice_id = _create_invoice_in_db(
        firm_id, client_id, total_amount="1000.00", stripe_payment_intent_id="pi_test_partial"
    )

    fake_event = {
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_test_partial",
                "metadata": {"invoice_id": str(invoice_id)},
                "amount_received": 50000,
                "latest_charge": "ch_test_partial",
            }
        },
    }

    with patch(_WEBHOOK_MOCK, return_value=fake_event), \
         patch("app.services.invoice_service.log_event") as mock_log:
        r = client.post(
            "/payments/webhook",
            content=b'{"type":"payment_intent.succeeded"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    assert r.status_code == 200, r.text

    assert mock_log.called
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["event_type"] == "invoice.partial_payment"
    assert call_kwargs["metadata"]["amount_paid"] == "500.0"
    assert call_kwargs["metadata"]["remaining_balance"] == "500.0"

    db = TestingSessionLocal()
    try:
        inv = db.get(Invoice, invoice_id)
        assert inv.status == InvoiceStatus.partial
        assert Decimal(str(inv.amount_paid)) == Decimal("500.00")
    finally:
        db.close()


def test_webhook_successive_partial_payments_accumulate(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    client_id = _create_client_in_db(firm_id)
    invoice_id = _create_invoice_in_db(
        firm_id, client_id, total_amount="1000.00", stripe_payment_intent_id="pi_test_accum"
    )

    def _fake_event(amount_received_cents):
        return {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_test_accum",
                    "metadata": {"invoice_id": str(invoice_id)},
                    "amount_received": amount_received_cents,
                    "latest_charge": "ch_test_accum",
                }
            },
        }

    with patch(_WEBHOOK_MOCK, return_value=_fake_event(50000)), \
         patch("app.services.invoice_service.log_event") as mock_log_1:
        r1 = client.post(
            "/payments/webhook",
            content=b'{"type":"payment_intent.succeeded"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )
    assert r1.status_code == 200, r1.text
    call_kwargs_1 = mock_log_1.call_args.kwargs
    assert call_kwargs_1["metadata"]["amount_paid"] == "500.0"
    assert call_kwargs_1["metadata"]["remaining_balance"] == "500.0"

    with patch(_WEBHOOK_MOCK, return_value=_fake_event(30000)), \
         patch("app.services.invoice_service.log_event") as mock_log_2:
        r2 = client.post(
            "/payments/webhook",
            content=b'{"type":"payment_intent.succeeded"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )
    assert r2.status_code == 200, r2.text
    call_kwargs_2 = mock_log_2.call_args.kwargs
    assert call_kwargs_2["event_type"] == "invoice.partial_payment"
    assert call_kwargs_2["metadata"]["amount_paid"] == "800.0"
    assert call_kwargs_2["metadata"]["remaining_balance"] == "200.0"

    db = TestingSessionLocal()
    try:
        inv = db.get(Invoice, invoice_id)
        assert inv.status == InvoiceStatus.partial
        assert Decimal(str(inv.amount_paid)) == Decimal("800.00")
    finally:
        db.close()


def test_webhook_refund_fires_event_and_updates_invoice(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    client_id = _create_client_in_db(firm_id)
    invoice_id = _create_invoice_in_db(
        firm_id,
        client_id,
        total_amount="1000.00",
        status=InvoiceStatus.paid,
        paid_at=datetime.now(timezone.utc),
        stripe_payment_intent_id="pi_test_refund",
    )

    fake_event = {
        "type": "charge.refunded",
        "data": {
            "object": {
                "id": "ch_test_refund",
                "metadata": {"invoice_id": str(invoice_id)},
                "amount_refunded": 25000,
                "refunds": {"data": [{"reason": "requested_by_customer"}]},
            }
        },
    }

    with patch(_WEBHOOK_MOCK, return_value=fake_event), \
         patch("app.services.invoice_service.log_event") as mock_log:
        r = client.post(
            "/payments/webhook",
            content=b'{"type":"charge.refunded"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    assert r.status_code == 200, r.text

    assert mock_log.called
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["event_type"] == "invoice.refunded"
    assert call_kwargs["metadata"]["amount_refunded"] == "250.0"
    assert call_kwargs["metadata"]["reason"] == "requested_by_customer"

    db = TestingSessionLocal()
    try:
        inv = db.get(Invoice, invoice_id)
        assert inv.status == InvoiceStatus.refunded
        assert Decimal(str(inv.refunded_amount)) == Decimal("250.00")
    finally:
        db.close()


def test_webhook_payment_failed_fires_event_without_changing_status(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    client_id = _create_client_in_db(firm_id)
    invoice_id = _create_invoice_in_db(
        firm_id, client_id, total_amount="1000.00", stripe_payment_intent_id="pi_test_failed_real"
    )

    fake_event = {
        "type": "payment_intent.payment_failed",
        "data": {
            "object": {
                "id": "pi_test_failed_real",
                "metadata": {"invoice_id": str(invoice_id)},
                "last_payment_error": {
                    "code": "card_declined",
                    "message": "Your card was declined.",
                },
            }
        },
    }

    with patch(_WEBHOOK_MOCK, return_value=fake_event), \
         patch("app.services.invoice_service.log_event") as mock_log:
        r = client.post(
            "/payments/webhook",
            content=b'{"type":"payment_intent.payment_failed"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    assert r.status_code == 200, r.text

    assert mock_log.called
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["event_type"] == "invoice.payment_failed"
    assert call_kwargs["metadata"]["failure_code"] == "card_declined"
    assert call_kwargs["metadata"]["failure_message"] == "Your card was declined."

    db = TestingSessionLocal()
    try:
        inv = db.get(Invoice, invoice_id)
        assert inv.status == InvoiceStatus.sent
    finally:
        db.close()


def test_webhook_account_updated_fires_status_changed_event(client, firm_a_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])

    db = TestingSessionLocal()
    try:
        conn = StripeConnection(
            firm_id=firm_id,
            stripe_account_id="acct_test_status_changed",
            charges_enabled=False,
            payouts_enabled=False,
            details_submitted=False,
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)
        account_id = conn.stripe_account_id
    finally:
        db.close()

    fake_event = {
        "type": "account.updated",
        "data": {
            "object": {
                "id": account_id,
                "charges_enabled": True,
                "payouts_enabled": False,
                "details_submitted": True,
            }
        },
    }

    with patch(_WEBHOOK_MOCK, return_value=fake_event), \
         patch("app.services.stripe_service.log_event") as mock_log:
        r = client.post(
            "/payments/webhook",
            content=b'{"type":"account.updated"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    assert r.status_code == 200, r.text

    assert mock_log.called
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["event_type"] == "stripe.account_status_changed"
    assert call_kwargs["metadata"]["charges_enabled"] is True
    assert call_kwargs["metadata"]["payouts_enabled"] is False
    assert call_kwargs["metadata"]["details_submitted"] is True
    assert set(call_kwargs["metadata"]["changed"]) == {"charges_enabled", "details_submitted"}


# ===========================================================================
# GROUP 5 — Tenant isolation
# ===========================================================================

def test_firm_cannot_see_other_firm_invoice(client, firm_a_owner, firm_b_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers_a = firm_a_owner["headers"]
    headers_b = firm_b_owner["headers"]
    client_id = _create_client_in_db(firm_id)

    invoice_id = client.post("/invoices/", json=_invoice_payload(client_id), headers=headers_a).json()["id"]

    r = client.get(f"/invoices/{invoice_id}", headers=headers_b)
    assert r.status_code == 404, r.text


def test_firm_cannot_update_other_firm_invoice(client, firm_a_owner, firm_b_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers_a = firm_a_owner["headers"]
    headers_b = firm_b_owner["headers"]
    client_id = _create_client_in_db(firm_id)

    invoice_id = client.post("/invoices/", json=_invoice_payload(client_id), headers=headers_a).json()["id"]

    r = client.patch(
        f"/invoices/{invoice_id}",
        json={"notes_client_visible": "cross-firm attack"},
        headers=headers_b,
    )
    assert r.status_code == 404, r.text


def test_firm_cannot_delete_other_firm_invoice(client, firm_a_owner, firm_b_owner):
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers_a = firm_a_owner["headers"]
    headers_b = firm_b_owner["headers"]
    client_id = _create_client_in_db(firm_id)

    invoice_id = client.post("/invoices/", json=_invoice_payload(client_id), headers=headers_a).json()["id"]

    r = client.delete(f"/invoices/{invoice_id}", headers=headers_b)
    assert r.status_code == 404, r.text


# ===========================================================================
# GROUP 6 — Portal billing
# ===========================================================================

def test_portal_cannot_see_draft_invoice(client):
    firm_id, firm_slug, _ = _make_firm_and_staff(
        slug="portal-draft-firm", staff_email="draft_staff@firm.com"
    )
    portal_client_id = _make_portal_client(firm_id, email="draft_client@example.com")
    staff_headers = _staff_login(client, "draft_staff@firm.com")

    # Create a draft invoice for this client via staff API
    invoice_id = client.post(
        "/invoices/", json=_invoice_payload(portal_client_id), headers=staff_headers
    ).json()["id"]

    # Login as portal client
    login_r = _portal_login(client, firm_slug, "draft_client@example.com")
    assert login_r.status_code == 200, login_r.text
    token = login_r.json()["access_token"]

    # Draft invoice must NOT appear in portal listing
    r = client.get("/portal/invoices", headers=_portal_headers(token))
    assert r.status_code == 200, r.text
    ids = [inv["id"] for inv in r.json()["items"]]
    assert invoice_id not in ids


def test_portal_can_see_sent_invoice(client):
    firm_id, firm_slug, _ = _make_firm_and_staff(
        slug="portal-sent-firm", staff_email="sent_staff@firm.com"
    )
    portal_client_id = _make_portal_client(firm_id, email="sent_client@example.com")
    staff_headers = _staff_login(client, "sent_staff@firm.com")

    # Create and send invoice
    payload = {**_invoice_payload(portal_client_id), "due_date": date(2026, 8, 1).isoformat()}
    invoice_id = client.post(
        "/invoices/", json=payload, headers=staff_headers
    ).json()["id"]
    send_r = client.post(f"/invoices/{invoice_id}/send", headers=staff_headers)
    assert send_r.status_code == 200, send_r.text

    # Login as portal client
    login_r = _portal_login(client, firm_slug, "sent_client@example.com")
    assert login_r.status_code == 200, login_r.text
    token = login_r.json()["access_token"]

    # Sent invoice MUST appear in portal listing
    r = client.get("/portal/invoices", headers=_portal_headers(token))
    assert r.status_code == 200, r.text
    ids = [inv["id"] for inv in r.json()["items"]]
    assert invoice_id in ids


def test_portal_cannot_see_other_client_invoice(client):
    firm_id, firm_slug, _ = _make_firm_and_staff(
        slug="portal-isolation-firm", staff_email="iso_staff@firm.com"
    )
    client_a_id = _make_portal_client(firm_id, email="client_a@example.com", password="PassA1!")
    client_b_id = _make_portal_client(firm_id, email="client_b@example.com", password="PassB1!")
    staff_headers = _staff_login(client, "iso_staff@firm.com")

    # Create and send invoice for Client A
    invoice_a_id = client.post(
        "/invoices/", json=_invoice_payload(client_a_id), headers=staff_headers
    ).json()["id"]
    client.post(f"/invoices/{invoice_a_id}/send", headers=staff_headers)

    # Login as Client B and attempt to access Client A's invoice directly
    login_r = _portal_login(client, firm_slug, "client_b@example.com", "PassB1!")
    assert login_r.status_code == 200, login_r.text
    token_b = login_r.json()["access_token"]

    r = client.get(f"/portal/invoices/{invoice_a_id}", headers=_portal_headers(token_b))
    assert r.status_code == 404, r.text


@pytest.mark.skip(reason="WeasyPrint requires GTK")
def test_portal_pdf_download(client):
    firm_id, firm_slug, _ = _make_firm_and_staff(
        slug="portal-pdf-firm", staff_email="pdf_staff@firm.com"
    )
    portal_client_id = _make_portal_client(firm_id, email="pdf_client@example.com")
    staff_headers = _staff_login(client, "pdf_staff@firm.com")

    # Create and send invoice
    invoice_id = client.post(
        "/invoices/", json=_invoice_payload(portal_client_id), headers=staff_headers
    ).json()["id"]
    client.post(f"/invoices/{invoice_id}/send", headers=staff_headers)

    # Login as portal client
    login_r = _portal_login(client, firm_slug, "pdf_client@example.com")
    assert login_r.status_code == 200, login_r.text
    token = login_r.json()["access_token"]

    r = client.get(f"/portal/invoices/{invoice_id}/pdf", headers=_portal_headers(token))
    assert r.status_code == 200
    assert "application/pdf" in r.headers["content-type"]


# ===========================================================================
# GROUP 7 — Stripe Connect redirect URI (settings-driven)
# ===========================================================================

def test_get_connect_url_uses_configured_domain(monkeypatch):
    from app.core.config import get_settings
    from app.services import stripe_service

    settings = get_settings()
    monkeypatch.setattr(settings, "stripe_connect_client_id", "ca_test_123")

    url = stripe_service.get_connect_url(uuid.uuid4(), "state123")

    assert "api.jammpx.com" in url
    assert "jammos" not in url


def test_get_connect_url_respects_settings_override(monkeypatch):
    from app.core.config import get_settings
    from app.services import stripe_service

    settings = get_settings()
    monkeypatch.setattr(settings, "stripe_connect_client_id", "ca_test_123")
    monkeypatch.setattr(
        settings, "stripe_connect_redirect_uri", "https://staging.jammpx.com/stripe/callback"
    )

    url = stripe_service.get_connect_url(uuid.uuid4(), "state123")

    assert "redirect_uri=https://staging.jammpx.com/stripe/callback" in url
