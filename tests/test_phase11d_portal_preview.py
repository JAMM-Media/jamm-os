# tests/test_phase11d_portal_preview.py

"""
Phase 11D — Portal Preview test suite.

Tests the GET /portal/preview/{client_id} endpoint that lets staff see
exactly what a client would see in their portal, without logging in as
the client.
"""

import uuid

from tests.conftest import TestingSessionLocal
from app.models.client import Client
from app.models.document import Document
from app.models.document_request import DocumentRequest
from app.models.engagement import Engagement
from app.models.firm import Firm
from app.models.invoice import Invoice
from app.models.user import User
from app.core.enums import InvoiceStatus, UserRole
from app.core.security import get_password_hash
from app.crud.message import create_message
from app.services.portal_auth import hash_portal_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_firm_and_owner(name: str, slug: str, email: str, password: str = "pass1234") -> dict:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=name, slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)

        owner = User(
            firm_id=firm.id,
            email=email,
            hashed_password=get_password_hash(password),
            full_name="Owner User",
            role=UserRole.firm_owner,
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)

        return {
            "firm_id": firm.id,
            "firm_slug": firm.slug,
            "owner_id": owner.id,
            "owner_email": email,
            "owner_password": password,
        }
    finally:
        db.close()


def _create_staff_user(firm_id: uuid.UUID, email: str, password: str = "staffpass") -> dict:
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=email,
            hashed_password=get_password_hash(password),
            full_name="Staff User",
            role=UserRole.staff,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"user_id": user.id, "email": email, "password": password}
    finally:
        db.close()


def _create_client(firm_id: uuid.UUID, name: str = "Test Client",
                   email: str = None, portal_password: str = "portalpass1") -> dict:
    db = TestingSessionLocal()
    try:
        client_email = email or f"client-{uuid.uuid4().hex[:6]}@example.com"
        client = Client(
            firm_id=firm_id,
            name=name,
            email=client_email,
            portal_password_hash=hash_portal_password(portal_password),
            portal_access_enabled=True,
        )
        db.add(client)
        db.commit()
        db.refresh(client)
        return {
            "client_id": client.id,
            "email": client_email,
            "portal_password": portal_password,
        }
    finally:
        db.close()


def _create_engagement(firm_id: uuid.UUID, client_id: uuid.UUID, name: str = "Test Engagement") -> uuid.UUID:
    db = TestingSessionLocal()
    try:
        eng = Engagement(firm_id=firm_id, client_id=client_id, name=name)
        db.add(eng)
        db.commit()
        db.refresh(eng)
        return eng.id
    finally:
        db.close()


def _seed_data(firm_id: uuid.UUID, client_id: uuid.UUID, owner_id: uuid.UUID) -> dict:
    """
    Seed the database for portal preview tests:
    - 1 engagement (required FK for documents/doc requests)
    - 2 document requests (one empty, one with items)
    - 2 documents
    - 1 draft invoice + 1 sent invoice
    - 1 staff message + 1 client message
    """
    db = TestingSessionLocal()
    try:
        # Engagement
        eng = Engagement(firm_id=firm_id, client_id=client_id, name="Preview Engagement")
        db.add(eng)
        db.flush()

        # Document request 1 — no checklist items
        dr1 = DocumentRequest(
            firm_id=firm_id,
            client_id=client_id,
            engagement_id=eng.id,
            title="Empty Request",
            checklist_items=[],
            status="pending",
        )
        db.add(dr1)

        # Document request 2 — 3 items, 1 approved
        dr2 = DocumentRequest(
            firm_id=firm_id,
            client_id=client_id,
            engagement_id=eng.id,
            title="Request With Items",
            checklist_items=[
                {"id": str(uuid.uuid4()), "label": "W-2", "is_required": True, "status": "approved"},
                {"id": str(uuid.uuid4()), "label": "1099", "is_required": True, "status": "pending"},
                {"id": str(uuid.uuid4()), "label": "Bank stmt", "is_required": False, "status": "pending"},
            ],
            status="partial",
        )
        db.add(dr2)

        # Document 1
        doc1 = Document(
            firm_id=firm_id,
            client_id=client_id,
            engagement_id=eng.id,
            uploaded_by=owner_id,
            filename="tax_return.pdf",
            s3_key=f"{firm_id}/{client_id}/{eng.id}/{uuid.uuid4()}/tax_return.pdf",
            content_type="application/pdf",
            size_bytes=1024,
        )
        db.add(doc1)

        # Document 2
        doc2 = Document(
            firm_id=firm_id,
            client_id=client_id,
            engagement_id=eng.id,
            uploaded_by=owner_id,
            filename="invoice_summary.xlsx",
            s3_key=f"{firm_id}/{client_id}/{eng.id}/{uuid.uuid4()}/invoice_summary.xlsx",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            size_bytes=2048,
        )
        db.add(doc2)

        # Draft invoice (should NOT appear in preview)
        inv_draft = Invoice(
            firm_id=firm_id,
            client_id=client_id,
            invoice_number="INV-001",
            subtotal=500.00,
            tax_rate=0.0,
            tax_amount=0.0,
            total_amount=500.00,
            status=InvoiceStatus.draft,
        )
        db.add(inv_draft)

        # Sent invoice (should appear in preview)
        inv_sent = Invoice(
            firm_id=firm_id,
            client_id=client_id,
            invoice_number="INV-002",
            subtotal=750.00,
            tax_rate=0.0,
            tax_amount=0.0,
            total_amount=750.00,
            status=InvoiceStatus.sent,
        )
        db.add(inv_sent)

        db.commit()

        # Messages — created after commit so IDs are resolved
        staff_msg = create_message(
            db,
            firm_id=firm_id,
            client_id=client_id,
            sender_id=owner_id,
            sender_role="staff",
            body="Hello from staff",
        )
        client_msg = create_message(
            db,
            firm_id=firm_id,
            client_id=client_id,
            sender_id=None,
            sender_role="client",
            body="Hello from client",
        )

        return {
            "engagement_id": eng.id,
            "dr1_id": dr1.id,
            "dr2_id": dr2.id,
            "doc1_id": doc1.id,
            "doc2_id": doc2.id,
            "inv_draft_id": inv_draft.id,
            "inv_sent_id": inv_sent.id,
            "staff_msg_id": staff_msg.id,
            "client_msg_id": client_msg.id,
        }
    finally:
        db.close()


def _login_staff(http_client, email: str, password: str) -> dict:
    r = http_client.post("/auth/token", json={"username": email, "password": password})
    assert r.status_code == 200, f"Staff login failed: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _login_portal(http_client, firm_slug: str, email: str, password: str) -> dict:
    r = http_client.post("/portal/auth/login", json={
        "email": email,
        "firm_slug": firm_slug,
        "password": password,
    })
    assert r.status_code == 200, f"Portal login failed: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup(http_client) -> dict:
    uid = uuid.uuid4().hex[:6]

    # Firm A
    firm_a = _create_firm_and_owner(
        f"Preview Firm A {uid}", f"preview-firm-a-{uid}",
        f"owner-a-{uid}@preview.com",
    )
    staff_a = _create_staff_user(firm_a["firm_id"], f"staff-a-{uid}@preview.com")
    client_a = _create_client(firm_a["firm_id"], name="Portal Preview Client",
                               email=f"client-a-{uid}@example.com")

    seed = _seed_data(firm_a["firm_id"], client_a["client_id"], firm_a["owner_id"])

    owner_a_headers = _login_staff(http_client, firm_a["owner_email"], firm_a["owner_password"])
    staff_a_headers = _login_staff(http_client, staff_a["email"], staff_a["password"])
    portal_a_headers = _login_portal(http_client, firm_a["firm_slug"],
                                      client_a["email"], client_a["portal_password"])

    # Firm B (for tenant isolation test)
    firm_b = _create_firm_and_owner(
        f"Preview Firm B {uid}", f"preview-firm-b-{uid}",
        f"owner-b-{uid}@preview.com",
    )
    client_b = _create_client(firm_b["firm_id"], name="Firm B Client",
                               email=f"client-b-{uid}@example.com")
    owner_b_headers = _login_staff(http_client, firm_b["owner_email"], firm_b["owner_password"])

    return {
        "firm_a_id": firm_a["firm_id"],
        "firm_b_id": firm_b["firm_id"],
        "client_a_id": client_a["client_id"],
        "client_b_id": client_b["client_id"],
        "owner_a_headers": owner_a_headers,
        "staff_a_headers": staff_a_headers,
        "portal_a_headers": portal_a_headers,
        "owner_b_headers": owner_b_headers,
        "seed": seed,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_portal_preview_returns_200(client):
    """firm_owner fetches preview — 200, correct client_name, expected structure."""
    ctx = _setup(client)
    client_id = str(ctx["client_a_id"])

    r = client.get(f"/portal/preview/{client_id}", headers=ctx["owner_a_headers"])
    assert r.status_code == 200, r.text

    data = r.json()
    assert data["client_id"] == client_id
    assert data["client_name"] == "Portal Preview Client"
    assert "document_requests" in data
    assert "documents" in data
    assert "invoices" in data
    assert "messages" in data
    assert "generated_at" in data


def test_portal_preview_document_requests(client):
    """Preview includes both document requests with correct item counts."""
    ctx = _setup(client)
    client_id = str(ctx["client_a_id"])

    r = client.get(f"/portal/preview/{client_id}", headers=ctx["owner_a_headers"])
    assert r.status_code == 200, r.text

    drs = r.json()["document_requests"]
    assert len(drs) == 2

    # Identify each request by title
    by_title = {dr["title"]: dr for dr in drs}

    empty_dr = by_title["Empty Request"]
    assert empty_dr["items_total"] == 0
    assert empty_dr["items_completed"] == 0

    items_dr = by_title["Request With Items"]
    assert items_dr["items_total"] == 3
    assert items_dr["items_completed"] == 1


def test_portal_preview_documents(client):
    """Preview includes 2 client_visible documents."""
    ctx = _setup(client)
    client_id = str(ctx["client_a_id"])

    r = client.get(f"/portal/preview/{client_id}", headers=ctx["owner_a_headers"])
    assert r.status_code == 200, r.text

    docs = r.json()["documents"]
    assert len(docs) == 2

    # Each document must have the required fields
    for doc in docs:
        assert "id" in doc
        assert "name" in doc
        assert "uploaded_at" in doc
        assert "visibility" in doc
        assert doc["visibility"] == "client_visible"


def test_portal_preview_excludes_draft_invoice(client):
    """Only the sent invoice appears — the draft invoice is excluded."""
    ctx = _setup(client)
    client_id = str(ctx["client_a_id"])
    seed = ctx["seed"]

    r = client.get(f"/portal/preview/{client_id}", headers=ctx["owner_a_headers"])
    assert r.status_code == 200, r.text

    invoices = r.json()["invoices"]
    assert len(invoices) == 1

    inv = invoices[0]
    assert inv["invoice_number"] == "INV-002"
    assert inv["status"] == "sent"
    assert float(inv["amount_due"]) == 750.00

    # Draft invoice must not be present
    invoice_ids = [i["id"] for i in invoices]
    assert str(seed["inv_draft_id"]) not in invoice_ids


def test_portal_preview_message_summary(client):
    """unread_count and last_message_at are present and correct."""
    ctx = _setup(client)
    client_id = str(ctx["client_a_id"])

    r = client.get(f"/portal/preview/{client_id}", headers=ctx["owner_a_headers"])
    assert r.status_code == 200, r.text

    msgs = r.json()["messages"]
    # 1 staff-sent message, not yet read by client → unread_count = 1
    assert msgs["unread_count"] == 1
    assert msgs["last_message_at"] is not None


def test_portal_preview_staff_can_access(client):
    """A staff role (not firm_owner) can also fetch the preview."""
    ctx = _setup(client)
    client_id = str(ctx["client_a_id"])

    r = client.get(f"/portal/preview/{client_id}", headers=ctx["staff_a_headers"])
    assert r.status_code == 200, r.text
    assert r.json()["client_id"] == client_id


def test_portal_preview_client_portal_user_forbidden(client):
    """A client_portal_user JWT is rejected with 403."""
    ctx = _setup(client)
    client_id = str(ctx["client_a_id"])

    r = client.get(f"/portal/preview/{client_id}", headers=ctx["portal_a_headers"])
    assert r.status_code in (401, 403), r.text


def test_portal_preview_wrong_firm(client):
    """Firm A staff cannot preview a Firm B client — tenant isolation."""
    ctx = _setup(client)
    # Use Firm A owner headers to try to preview Firm B client
    client_b_id = str(ctx["client_b_id"])

    r = client.get(f"/portal/preview/{client_b_id}", headers=ctx["owner_a_headers"])
    assert r.status_code == 404, r.text


def test_portal_preview_client_not_found(client):
    """404 if the client_id does not exist."""
    ctx = _setup(client)
    nonexistent_id = str(uuid.uuid4())

    r = client.get(f"/portal/preview/{nonexistent_id}", headers=ctx["owner_a_headers"])
    assert r.status_code == 404, r.text
