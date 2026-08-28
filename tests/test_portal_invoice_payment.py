# tests/test_portal_invoice_payment.py
"""
Tests for portal invoice payment status guard.

Before the fix: only InvoiceStatus.sent was allowed through the status check.
After the fix: InvoiceStatus.sent and InvoiceStatus.overdue are both allowed.

The payment flow reaches the Stripe connection check AFTER the status check.
In the test environment there is no connected Stripe account, so the expected
outcome for a sent or overdue invoice is a 400 "Payment not available for this
invoice" (Stripe connection check). Paid, draft, and void invoices are rejected
BEFORE reaching Stripe with a distinct 400 "This invoice is not available for
payment" (status guard).

Negative controls confirm the two 400 messages are distinct, ensuring the test
is actually watching the status guard and not some other failure path.
"""

import uuid

from app.core.enums import InvoiceDeliveryMethod, InvoiceStatus
from app.models.client import Client
from app.models.firm import Firm
from app.models.invoice import Invoice
from app.services.portal_auth import hash_portal_password
from tests.conftest import TestingSessionLocal

STATUS_GUARD_MSG = "This invoice is not available for payment"
STRIPE_CONN_MSG = "Payment not available for this invoice"


def _create_portal_client(firm_id: str) -> dict:
    email = f"inv-pay-{uuid.uuid4().hex[:8]}@example.com"
    password = "testpass1!"
    db = TestingSessionLocal()
    try:
        c = Client(
            firm_id=uuid.UUID(firm_id),
            name="Invoice Pay Test Client",
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


def _create_invoice(firm_id: str, client_id: str, status: InvoiceStatus) -> str:
    db = TestingSessionLocal()
    try:
        inv = Invoice(
            firm_id=uuid.UUID(firm_id),
            client_id=uuid.UUID(client_id),
            invoice_number=f"TEST-{uuid.uuid4().hex[:6].upper()}",
            line_items=[{
                "id": str(uuid.uuid4()),
                "description": "Test service",
                "quantity": 1,
                "unit_price": 100.0,
                "total": 100.0,
            }],
            subtotal=100.0,
            tax_rate=0.0,
            tax_amount=0.0,
            total_amount=100.0,
            status=status,
            delivery_method=InvoiceDeliveryMethod.portal,
            is_deleted=False,
        )
        db.add(inv)
        db.commit()
        db.refresh(inv)
        return str(inv.id)
    finally:
        db.close()


def test_overdue_invoice_passes_status_guard(client, firm_a_owner):
    """
    An overdue invoice must pass the status guard and reach the Stripe connection
    check, not be rejected by the status check itself.

    The test environment has no connected Stripe account, so the expected outcome
    is a 400 from the STRIPE connection check (STRIPE_CONN_MSG), not from the
    status guard (STATUS_GUARD_MSG). Receiving STRIPE_CONN_MSG confirms the fix:
    the status guard no longer blocks overdue invoices.
    """
    firm_id = firm_a_owner["firm_id"]
    portal = _create_portal_client(firm_id)
    headers = _portal_login(client, firm_id, portal["email"], portal["password"])
    inv_id = _create_invoice(firm_id, portal["client_id"], InvoiceStatus.overdue)

    r = client.post(f"/portal/invoices/{inv_id}/pay", headers=headers)

    assert r.status_code == 400, r.json()
    detail = r.json().get("detail", "")
    assert detail != STATUS_GUARD_MSG, (
        f"Status guard fired on an overdue invoice -- the fix did not take effect. "
        f"Got: {detail!r}"
    )
    assert detail == STRIPE_CONN_MSG, (
        f"Expected Stripe connection rejection but got unexpected detail: {detail!r}"
    )


def test_sent_invoice_still_passes_status_guard(client, firm_a_owner):
    """Regression: sent invoices must still pass the status guard after the fix."""
    firm_id = firm_a_owner["firm_id"]
    portal = _create_portal_client(firm_id)
    headers = _portal_login(client, firm_id, portal["email"], portal["password"])
    inv_id = _create_invoice(firm_id, portal["client_id"], InvoiceStatus.sent)

    r = client.post(f"/portal/invoices/{inv_id}/pay", headers=headers)

    assert r.status_code == 400, r.json()
    detail = r.json().get("detail", "")
    assert detail != STATUS_GUARD_MSG, (
        f"Status guard fired on a sent invoice -- regression. Got: {detail!r}"
    )


def test_paid_invoice_is_rejected_by_status_guard(client, firm_a_owner):
    """Paid invoices must still be rejected immediately by the status guard."""
    firm_id = firm_a_owner["firm_id"]
    portal = _create_portal_client(firm_id)
    headers = _portal_login(client, firm_id, portal["email"], portal["password"])
    inv_id = _create_invoice(firm_id, portal["client_id"], InvoiceStatus.paid)

    r = client.post(f"/portal/invoices/{inv_id}/pay", headers=headers)

    assert r.status_code == 400, r.json()
    assert r.json()["detail"] == STATUS_GUARD_MSG


def test_draft_invoice_cannot_be_paid(client, firm_a_owner):
    """
    Draft invoices must not be payable. Draft is not in _PORTAL_VISIBLE_STATUSES,
    so the portal get_portal_invoice query returns None before pay_invoice() is
    reached. The endpoint returns 404 "Invoice not found".
    """
    firm_id = firm_a_owner["firm_id"]
    portal = _create_portal_client(firm_id)
    headers = _portal_login(client, firm_id, portal["email"], portal["password"])
    inv_id = _create_invoice(firm_id, portal["client_id"], InvoiceStatus.draft)

    r = client.post(f"/portal/invoices/{inv_id}/pay", headers=headers)

    assert r.status_code == 404, r.json()
    assert r.json()["detail"] == "Invoice not found"


def test_void_invoice_cannot_be_paid(client, firm_a_owner):
    """
    Void invoices must not be payable. Void is not in _PORTAL_VISIBLE_STATUSES,
    so the portal get_portal_invoice query returns None before pay_invoice() is
    reached. The endpoint returns 404 "Invoice not found".
    """
    firm_id = firm_a_owner["firm_id"]
    portal = _create_portal_client(firm_id)
    headers = _portal_login(client, firm_id, portal["email"], portal["password"])
    inv_id = _create_invoice(firm_id, portal["client_id"], InvoiceStatus.void)

    r = client.post(f"/portal/invoices/{inv_id}/pay", headers=headers)

    assert r.status_code == 404, r.json()
    assert r.json()["detail"] == "Invoice not found"


# ===========================================================================
# EMAIL COPY ENDPOINT TESTS
# POST /portal/invoices/{invoice_id}/email
# ===========================================================================

def test_client_can_email_own_invoice(client, firm_a_owner, mock_email_service):
    """
    A client requesting an email copy of their own invoice receives 200 {"sent": true}
    and the underlying EmailService._send is invoked with the authenticated client's
    own email address.
    """
    firm_id = firm_a_owner["firm_id"]
    portal = _create_portal_client(firm_id)
    headers = _portal_login(client, firm_id, portal["email"], portal["password"])
    inv_id = _create_invoice(firm_id, portal["client_id"], InvoiceStatus.sent)

    r = client.post(f"/portal/invoices/{inv_id}/email", headers=headers)

    assert r.status_code == 200, r.json()
    assert r.json() == {"sent": True}
    assert len(mock_email_service) == 1, (
        f"Expected exactly one email to be sent, got {len(mock_email_service)}"
    )
    assert mock_email_service[0]["to_email"] == portal["email"], (
        f"Email went to {mock_email_service[0]['to_email']!r}, expected {portal['email']!r}"
    )


def test_client_cannot_email_another_clients_invoice(client, firm_a_owner, mock_email_service):
    """
    A client requesting an email copy of an invoice that belongs to a different
    client (even within the same firm) receives 404. No email is sent.
    """
    firm_id = firm_a_owner["firm_id"]
    owner = _create_portal_client(firm_id)
    requester = _create_portal_client(firm_id)
    headers = _portal_login(client, firm_id, requester["email"], requester["password"])
    inv_id = _create_invoice(firm_id, owner["client_id"], InvoiceStatus.sent)

    r = client.post(f"/portal/invoices/{inv_id}/email", headers=headers)

    assert r.status_code == 404, r.json()
    assert r.json()["detail"] == "Invoice not found"
    assert len(mock_email_service) == 0, (
        f"No email should be sent when the invoice is not owned by the requester; "
        f"got {len(mock_email_service)} email(s)"
    )


def test_endpoint_ignores_email_in_request_body(client, firm_a_owner, mock_email_service):
    """
    If the client includes an 'email' field in the request body, the endpoint
    must ignore it and always send to the authenticated client's own address.
    This prevents the endpoint from being used as a relay for arbitrary addresses.
    """
    firm_id = firm_a_owner["firm_id"]
    portal = _create_portal_client(firm_id)
    headers = _portal_login(client, firm_id, portal["email"], portal["password"])
    inv_id = _create_invoice(firm_id, portal["client_id"], InvoiceStatus.sent)

    r = client.post(
        f"/portal/invoices/{inv_id}/email",
        headers=headers,
        json={"email": "attacker@evil.com"},
    )

    assert r.status_code == 200, r.json()
    assert r.json() == {"sent": True}
    assert len(mock_email_service) == 1
    assert mock_email_service[0]["to_email"] == portal["email"], (
        f"Email went to {mock_email_service[0]['to_email']!r} instead of the "
        f"authenticated client's address {portal['email']!r}"
    )
