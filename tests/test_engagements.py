# tests/test_engagements.py

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from tests.conftest import TestingSessionLocal
from app.core.enums import InvoiceStatus
from app.models.behavioral_event import BehavioralEvent
from app.models.document import Document
from app.models.engagement import Engagement
from app.models.invoice import Invoice
from app.models.time_entry import TimeEntry
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers for the delete_engagement attachment guard
# ---------------------------------------------------------------------------

def _make_client_and_engagement(http_client, headers, name="Guarded Engagement"):
    """Create a client and an engagement through the API. Returns (client_id, engagement_id)."""
    r = http_client.post("/clients/", json={"name": "Guard Client"}, headers=headers)
    assert r.status_code == 201, r.text
    client_id = r.json()["id"]

    r = http_client.post(
        "/engagements/",
        json={"client_id": client_id, "name": name},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return client_id, r.json()["id"]


def _attach_document(firm_id, client_id, engagement_id):
    db = TestingSessionLocal()
    try:
        doc = Document(
            firm_id=uuid.UUID(firm_id),
            client_id=uuid.UUID(client_id),
            engagement_id=uuid.UUID(engagement_id),
            filename="w2.pdf",
            s3_key=f"{firm_id}/{client_id}/{engagement_id}/{uuid.uuid4()}/w2.pdf",
            content_type="application/pdf",
            size_bytes=1024,
        )
        db.add(doc)
        db.commit()
    finally:
        db.close()


def _attach_time_entry(firm_id, engagement_id, user_email="owner@firma.com"):
    db = TestingSessionLocal()
    try:
        user = db.execute(
            select(User).where(User.email == user_email)
        ).scalars().first()
        entry = TimeEntry(
            firm_id=uuid.UUID(firm_id),
            engagement_id=uuid.UUID(engagement_id),
            user_id=user.id,
            description="Prepared return",
            hours=Decimal("2.00"),
            hourly_rate=Decimal("150.00"),
            date=date(2026, 3, 1),
        )
        db.add(entry)
        db.commit()
    finally:
        db.close()


def _attach_invoice(firm_id, client_id, engagement_id, is_deleted=False):
    db = TestingSessionLocal()
    try:
        inv = Invoice(
            firm_id=uuid.UUID(firm_id),
            client_id=uuid.UUID(client_id),
            engagement_id=uuid.UUID(engagement_id),
            invoice_number=f"INV-{uuid.uuid4().hex[:8]}",
            subtotal=Decimal("500.00"),
            tax_rate=Decimal("0.0"),
            tax_amount=Decimal("0.0"),
            total_amount=Decimal("500.00"),
            status=InvoiceStatus.draft,
            is_deleted=is_deleted,
        )
        db.add(inv)
        db.commit()
    finally:
        db.close()


def _engagement_row_exists(engagement_id):
    """Reads the table directly. An endpoint's own filtering could hide a row that is still there."""
    db = TestingSessionLocal()
    try:
        return db.get(Engagement, uuid.UUID(engagement_id)) is not None
    finally:
        db.close()


def test_create_and_get_engagement(client, firm_a_owner):
    headers = firm_a_owner["headers"]

    r = client.post("/clients/", json={"name": "Engagement Client"}, headers=headers)
    assert r.status_code == 201
    client_id = r.json()["id"]

    engagement_data = {
        "client_id": client_id,
        "name": "2024 Tax Return"
    }

    r = client.post("/engagements/", json=engagement_data, headers=headers)
    assert r.status_code == 201
    engagement = r.json()
    assert engagement["name"] == "2024 Tax Return"

    r = client.get(f"/engagements/{engagement['id']}", headers=headers)
    assert r.status_code == 200
    assert r.json()["name"] == "2024 Tax Return"


def test_create_engagement_missing_client_id(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    r = client.post("/engagements/", json={"name": "Orphan Engagement"}, headers=headers)
    assert r.status_code == 422


def test_get_nonexistent_engagement(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    r = client.get("/engagements/00000000-0000-0000-0000-000000000000", headers=headers)
    assert r.status_code == 404


def test_update_engagement(client, firm_a_owner):
    headers = firm_a_owner["headers"]

    r = client.post("/clients/", json={"name": "Update Client"}, headers=headers)
    assert r.status_code == 201
    client_id = r.json()["id"]

    r = client.post("/engagements/", json={"client_id": client_id, "name": "Original Name"}, headers=headers)
    assert r.status_code == 201
    engagement_id = r.json()["id"]

    r = client.patch(f"/engagements/{engagement_id}", json={"name": "Updated Name"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["name"] == "Updated Name"


def test_delete_engagement(client, firm_a_owner):
    headers = firm_a_owner["headers"]

    r = client.post("/clients/", json={"name": "Delete Client"}, headers=headers)
    assert r.status_code == 201
    client_id = r.json()["id"]

    r = client.post("/engagements/", json={"client_id": client_id, "name": "To Be Deleted"}, headers=headers)
    assert r.status_code == 201
    engagement_id = r.json()["id"]

    r = client.delete(f"/engagements/{engagement_id}", headers=headers)
    assert r.status_code == 204

    r = client.get(f"/engagements/{engagement_id}", headers=headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# delete_engagement attachment guard
#
# The delete is a hard delete: documents cascade away with the engagement and
# time entries cannot survive it at all. The guard in the service layer refuses
# the deletion while anything is still attached.
# ---------------------------------------------------------------------------

def test_delete_engagement_refused_with_attached_document(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]
    client_id, engagement_id = _make_client_and_engagement(client, headers)

    _attach_document(firm_id, client_id, engagement_id)

    r = client.delete(f"/engagements/{engagement_id}", headers=headers)
    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    assert "1 document" in detail, detail
    assert "Cannot delete engagement" in detail, detail
    assert _engagement_row_exists(engagement_id), "engagement was deleted despite the guard"


def test_delete_engagement_refused_with_attached_time_entry(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]
    _client_id, engagement_id = _make_client_and_engagement(client, headers)

    _attach_time_entry(firm_id, engagement_id)

    r = client.delete(f"/engagements/{engagement_id}", headers=headers)
    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    assert "1 time entry" in detail, detail
    assert _engagement_row_exists(engagement_id), "engagement was deleted despite the guard"


def test_delete_engagement_refused_with_attached_invoice(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]
    client_id, engagement_id = _make_client_and_engagement(client, headers)

    _attach_invoice(firm_id, client_id, engagement_id)

    r = client.delete(f"/engagements/{engagement_id}", headers=headers)
    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    assert "1 invoice" in detail, detail
    assert _engagement_row_exists(engagement_id), "engagement was deleted despite the guard"


def test_delete_engagement_refusal_names_every_attachment_with_counts(client, firm_a_owner):
    """The message has to be actionable, so it names each kind with its count."""
    headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]
    client_id, engagement_id = _make_client_and_engagement(client, headers)

    _attach_document(firm_id, client_id, engagement_id)
    _attach_document(firm_id, client_id, engagement_id)
    _attach_document(firm_id, client_id, engagement_id)
    _attach_time_entry(firm_id, engagement_id)
    _attach_time_entry(firm_id, engagement_id)
    _attach_invoice(firm_id, client_id, engagement_id)

    r = client.delete(f"/engagements/{engagement_id}", headers=headers)
    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    assert "3 documents" in detail, detail
    assert "2 time entries" in detail, detail
    assert "1 invoice" in detail, detail
    assert "Remove or reassign them first." in detail, detail


def test_delete_engagement_allowed_when_only_soft_deleted_invoice_attached(client, firm_a_owner):
    """A voided invoice is invisible everywhere else, so it must not block the delete."""
    headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]
    client_id, engagement_id = _make_client_and_engagement(client, headers)

    _attach_invoice(firm_id, client_id, engagement_id, is_deleted=True)

    r = client.delete(f"/engagements/{engagement_id}", headers=headers)
    assert r.status_code == 204, r.text
    assert not _engagement_row_exists(engagement_id)


def test_delete_engagement_succeeds_when_nothing_attached(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    _client_id, engagement_id = _make_client_and_engagement(client, headers)

    r = client.delete(f"/engagements/{engagement_id}", headers=headers)
    assert r.status_code == 204, r.text
    assert not _engagement_row_exists(engagement_id), "engagement row survived a successful delete"


def test_delete_engagement_fires_engagement_deleted_event(client, firm_a_owner):
    """The event names a hard delete, not an archive, because that is what happened."""
    headers = firm_a_owner["headers"]
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _client_id, engagement_id = _make_client_and_engagement(client, headers)

    r = client.delete(f"/engagements/{engagement_id}", headers=headers)
    assert r.status_code == 204, r.text

    db = TestingSessionLocal()
    try:
        rows = db.execute(
            select(BehavioralEvent).where(
                BehavioralEvent.firm_id == firm_id,
                BehavioralEvent.entity_id == uuid.UUID(engagement_id),
                BehavioralEvent.event_type == "engagement.deleted",
            )
        ).scalars().all()
        assert len(rows) == 1, f"expected 1 engagement.deleted event, got {len(rows)}"

        stale = db.execute(
            select(BehavioralEvent).where(
                BehavioralEvent.firm_id == firm_id,
                BehavioralEvent.event_type == "engagement.archived",
            )
        ).scalars().all()
        assert stale == [], "the old engagement.archived event is still being fired"
    finally:
        db.close()


def test_delete_engagement_fires_no_event_when_refused(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]
    client_id, engagement_id = _make_client_and_engagement(client, headers)

    _attach_document(firm_id, client_id, engagement_id)

    r = client.delete(f"/engagements/{engagement_id}", headers=headers)
    assert r.status_code == 400, r.text

    db = TestingSessionLocal()
    try:
        rows = db.execute(
            select(BehavioralEvent).where(
                BehavioralEvent.firm_id == uuid.UUID(firm_id),
                BehavioralEvent.entity_id == uuid.UUID(engagement_id),
                BehavioralEvent.event_type == "engagement.deleted",
            )
        ).scalars().all()
        assert rows == [], "a refused deletion still logged engagement.deleted"
    finally:
        db.close()
