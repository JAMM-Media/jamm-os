# tests/test_portal_preview_extensions.py

"""
Tests for the three new fields added to GET /portal/preview/{client_id}:
  - notifications (unread_count + recent list)
  - billing (total_invoiced, total_outstanding, invoice_count)
  - organizer (organizer_count, sent_count, in_progress_count, submitted_count)

Each section verifies real data and tenant isolation.
"""

import uuid
from datetime import datetime, timezone

import pytest

from tests.conftest import TestingSessionLocal
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.firm import Firm
from app.models.invoice import Invoice
from app.models.portal_notification import PortalNotification
from app.models.tax_organizer import TaxOrganizer, TaxOrganizerTemplate
from app.models.user import User
from app.core.enums import InvoiceStatus, UserRole
from app.core.security import get_password_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm_owner(name: str, slug: str, email: str) -> dict:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=name, slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)

        from app.services.tax_organizer_service import seed_firm_organizer_templates
        seed_firm_organizer_templates(firm_id=firm.id, db=db)

        user = User(
            firm_id=firm.id,
            email=email,
            hashed_password=get_password_hash("pass1234"),
            full_name="Test Owner",
            role=UserRole.firm_owner,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"firm_id": firm.id, "owner_email": email}
    finally:
        db.close()


def _make_client(firm_id: uuid.UUID) -> uuid.UUID:
    db = TestingSessionLocal()
    try:
        c = Client(
            firm_id=firm_id,
            name="Preview Test Client",
            email=f"prevclient-{uuid.uuid4()}@test.com",
            portal_access_enabled=True,
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        return c.id
    finally:
        db.close()


def _staff_headers(http_client, email: str) -> dict:
    r = http_client.post("/auth/token", json={"username": email, "password": "pass1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def test_preview_notifications_count_and_list(client):
    """Notifications field returns correct unread_count and recent items for the client."""
    fo = _make_firm_owner("Notif Firm", "notif-firm", "notifowner@notif.com")
    firm_id = fo["firm_id"]
    client_id = _make_client(firm_id)

    db = TestingSessionLocal()
    try:
        db.add(PortalNotification(
            firm_id=firm_id, client_id=client_id,
            title="Invoice ready", body="Your invoice is ready.",
            notification_type="payment_due", is_read=False,
        ))
        db.add(PortalNotification(
            firm_id=firm_id, client_id=client_id,
            title="Document uploaded", body=None,
            notification_type="document_request", is_read=True,
        ))
        db.commit()
    finally:
        db.close()

    headers = _staff_headers(client, fo["owner_email"])
    r = client.get(f"/portal/preview/{client_id}", headers=headers)
    assert r.status_code == 200, r.text

    data = r.json()
    assert "notifications" in data
    notifs = data["notifications"]
    assert notifs["unread_count"] == 1
    assert len(notifs["recent"]) == 2
    titles = {n["title"] for n in notifs["recent"]}
    assert "Invoice ready" in titles
    assert "Document uploaded" in titles


def test_preview_notifications_tenant_isolation(client):
    """Notifications from firm B are not returned in a firm A preview."""
    fo_a = _make_firm_owner("Notif Firm A", "notif-firm-a", "na@notifiso.com")
    fo_b = _make_firm_owner("Notif Firm B", "notif-firm-b", "nb@notifiso.com")
    client_a = _make_client(fo_a["firm_id"])
    client_b = _make_client(fo_b["firm_id"])

    db = TestingSessionLocal()
    try:
        db.add(PortalNotification(
            firm_id=fo_a["firm_id"], client_id=client_a,
            title="Firm A notification", body=None,
            notification_type="system", is_read=False,
        ))
        db.add(PortalNotification(
            firm_id=fo_b["firm_id"], client_id=client_b,
            title="Firm B notification", body=None,
            notification_type="system", is_read=False,
        ))
        db.commit()
    finally:
        db.close()

    headers_a = _staff_headers(client, fo_a["owner_email"])
    r = client.get(f"/portal/preview/{client_a}", headers=headers_a)
    assert r.status_code == 200, r.text

    titles = {n["title"] for n in r.json()["notifications"]["recent"]}
    assert "Firm A notification" in titles
    assert "Firm B notification" not in titles


# ---------------------------------------------------------------------------
# Billing summary
# ---------------------------------------------------------------------------

def test_preview_billing_totals(client):
    """Billing field sums total_invoiced and total_outstanding correctly."""
    fo = _make_firm_owner("Billing Firm", "billing-firm", "billingowner@billing.com")
    firm_id = fo["firm_id"]
    client_id = _make_client(firm_id)

    db = TestingSessionLocal()
    try:
        # Paid invoice: contributes to total_invoiced, not outstanding
        db.add(Invoice(
            firm_id=firm_id, client_id=client_id,
            invoice_number="INV-001", subtotal=1000.00, total_amount=1000.00,
            status=InvoiceStatus.paid, is_deleted=False,
        ))
        # Sent (unpaid) invoice: contributes to both total_invoiced and outstanding
        db.add(Invoice(
            firm_id=firm_id, client_id=client_id,
            invoice_number="INV-002", subtotal=500.00, total_amount=500.00,
            status=InvoiceStatus.sent, is_deleted=False,
        ))
        # Draft: excluded by service (status != draft filter)
        db.add(Invoice(
            firm_id=firm_id, client_id=client_id,
            invoice_number="INV-003", subtotal=9999.00, total_amount=9999.00,
            status=InvoiceStatus.draft, is_deleted=False,
        ))
        db.commit()
    finally:
        db.close()

    headers = _staff_headers(client, fo["owner_email"])
    r = client.get(f"/portal/preview/{client_id}", headers=headers)
    assert r.status_code == 200, r.text

    billing = r.json()["billing"]
    assert billing["invoice_count"] == 2          # excludes draft
    assert billing["total_invoiced"] == pytest.approx(1500.00)
    assert billing["total_outstanding"] == pytest.approx(500.00)  # only sent


def test_preview_billing_tenant_isolation(client):
    """Billing totals from firm B's invoices do not appear in firm A's preview."""
    fo_a = _make_firm_owner("Billing Firm A", "billing-firm-a", "ba@billingiso.com")
    fo_b = _make_firm_owner("Billing Firm B", "billing-firm-b", "bb@billingiso.com")
    client_a = _make_client(fo_a["firm_id"])
    client_b = _make_client(fo_b["firm_id"])

    db = TestingSessionLocal()
    try:
        db.add(Invoice(
            firm_id=fo_a["firm_id"], client_id=client_a,
            invoice_number="A-001", subtotal=200.00, total_amount=200.00,
            status=InvoiceStatus.sent, is_deleted=False,
        ))
        db.add(Invoice(
            firm_id=fo_b["firm_id"], client_id=client_b,
            invoice_number="B-001", subtotal=99999.00, total_amount=99999.00,
            status=InvoiceStatus.sent, is_deleted=False,
        ))
        db.commit()
    finally:
        db.close()

    headers_a = _staff_headers(client, fo_a["owner_email"])
    r = client.get(f"/portal/preview/{client_a}", headers=headers_a)
    assert r.status_code == 200, r.text

    billing = r.json()["billing"]
    assert billing["invoice_count"] == 1
    assert billing["total_invoiced"] == pytest.approx(200.00)


# ---------------------------------------------------------------------------
# Tax organizer summary
# ---------------------------------------------------------------------------

def test_preview_organizer_counts(client):
    """Organizer field returns correct counts for all three real statuses: sent, in_progress, submitted."""
    fo = _make_firm_owner("Org Firm", "org-firm", "orgowner@orgfirm.com")
    firm_id = fo["firm_id"]
    client_id = _make_client(firm_id)

    db = TestingSessionLocal()
    try:
        tmpl = db.query(TaxOrganizerTemplate).filter(
            TaxOrganizerTemplate.firm_id == firm_id
        ).first()
        template_id = tmpl.id if tmpl else None

        eng = Engagement(firm_id=firm_id, client_id=client_id, name="Org Test Engagement")
        db.add(eng)
        db.flush()

        # One of each real status value: sent, in_progress, submitted
        for status in ["sent", "in_progress", "submitted"]:
            db.add(TaxOrganizer(
                firm_id=firm_id,
                client_id=client_id,
                engagement_id=eng.id,
                template_id=template_id,
                status=status,
                responses={},
                tax_year=2024,
            ))
        db.commit()
    finally:
        db.close()

    headers = _staff_headers(client, fo["owner_email"])
    r = client.get(f"/portal/preview/{client_id}", headers=headers)
    assert r.status_code == 200, r.text

    org = r.json()["organizer"]
    assert org["organizer_count"] == 3
    assert org["sent_count"] == 1
    assert org["in_progress_count"] == 1
    assert org["submitted_count"] == 1


def test_preview_organizer_tenant_isolation(client):
    """Tax organizers belonging to firm B are not counted in firm A's preview."""
    fo_a = _make_firm_owner("Org Firm A", "org-firm-a", "oa@orgiso.com")
    fo_b = _make_firm_owner("Org Firm B", "org-firm-b", "ob@orgiso.com")
    client_a = _make_client(fo_a["firm_id"])
    client_b = _make_client(fo_b["firm_id"])

    db = TestingSessionLocal()
    try:
        tmpl_a = db.query(TaxOrganizerTemplate).filter(
            TaxOrganizerTemplate.firm_id == fo_a["firm_id"]
        ).first()
        tmpl_b = db.query(TaxOrganizerTemplate).filter(
            TaxOrganizerTemplate.firm_id == fo_b["firm_id"]
        ).first()

        eng_a = Engagement(firm_id=fo_a["firm_id"], client_id=client_a, name="Iso Eng A")
        eng_b = Engagement(firm_id=fo_b["firm_id"], client_id=client_b, name="Iso Eng B")
        db.add(eng_a)
        db.add(eng_b)
        db.flush()

        db.add(TaxOrganizer(
            firm_id=fo_a["firm_id"], client_id=client_a,
            engagement_id=eng_a.id,
            template_id=tmpl_a.id if tmpl_a else None,
            status="in_progress", responses={}, tax_year=2024,
        ))
        for _ in range(3):
            db.add(TaxOrganizer(
                firm_id=fo_b["firm_id"], client_id=client_b,
                engagement_id=eng_b.id,
                template_id=tmpl_b.id if tmpl_b else None,
                status="completed", responses={}, tax_year=2024,
            ))
        db.commit()
    finally:
        db.close()

    headers_a = _staff_headers(client, fo_a["owner_email"])
    r = client.get(f"/portal/preview/{client_a}", headers=headers_a)
    assert r.status_code == 200, r.text

    org = r.json()["organizer"]
    assert org["organizer_count"] == 1
    assert org["sent_count"] == 0
    assert org["in_progress_count"] == 1
    assert org["submitted_count"] == 0
