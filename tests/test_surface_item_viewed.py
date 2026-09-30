# tests/test_surface_item_viewed.py

"""
POST /surface-items/{item_id}/view and the surface_item.viewed event.

Ruled Sep 24, 2026. The name matches its neighbours, surface_item.dismissed
and surface_item.implemented, and one endpoint serves both surfaces: the
payload carries the surface kind, so the caller never needs a Briefing route
and an Observatory route.

The distinguishing property of this action is that it writes nothing. dismiss
and implement both stamp columns and commit; a view leaves surface_items
byte for byte as it found it and exists only in the event log. One test below
compares every column before and after for exactly that reason.

Every call fires. There is no dedup, because time to acted on is read from the
first view in the log, and a deduplicating writer would have to decide what
first means before anyone has asked the question.

log_event runs synchronously under JAMM_TESTING=1 (see behavioral_log), so
reading behavioral_events straight after a request is deterministic rather
than a race with a daemon thread.
"""

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select

from app.core.enums import InvoiceStatus, SurfaceKind
from app.models.behavioral_event import BehavioralEvent
from app.models.client import Client
from app.models.invoice import Invoice
from app.models.surface_item import SurfaceItem
from app.services.surface_daily_job import run_surface_generation_for_firm
from tests.conftest import TestingSessionLocal


VIEWED = "surface_item.viewed"


def _make_client(db, firm_id, name="Viewed Test Client"):
    row = Client(firm_id=firm_id, name=name, email=f"{uuid4().hex[:8]}@example.com")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _make_overdue_invoice(db, firm_id, client_id, days_overdue=10):
    invoice = Invoice(
        firm_id=firm_id,
        client_id=client_id,
        invoice_number=f"INV-{uuid4().hex[:8]}",
        subtotal=Decimal("500.00"),
        total_amount=Decimal("500.00"),
        amount_paid=Decimal("0.00"),
        status=InvoiceStatus.sent,
        due_date=date.today() - timedelta(days=days_overdue),
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


@pytest.fixture
def briefing_item(firm_a_owner):
    """Firm A with one generated briefing row, made the way the product makes
    them rather than inserted by hand."""
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        client_row = _make_client(db, firm_id)
        _make_overdue_invoice(db, firm_id, client_row.id)
    finally:
        db.close()

    db = TestingSessionLocal()
    try:
        run_surface_generation_for_firm(db, firm_id)
    finally:
        db.close()

    db = TestingSessionLocal()
    try:
        row = db.execute(
            select(SurfaceItem).where(
                SurfaceItem.firm_id == firm_id,
                SurfaceItem.kind == SurfaceKind.briefing,
            )
        ).scalars().first()
        assert row is not None, "the fixture generated no briefing row"
        return {**firm_a_owner, "item_id": str(row.id), "item_type": row.item_type}
    finally:
        db.close()


@pytest.fixture
def observatory_item(firm_a_owner):
    """An observatory row, written directly.

    The view endpoint does not care how a row came to exist, and the
    observatory generators need a longer history than this file should build
    to prove that a POST to one route fires with kind observatory.
    """
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        row = SurfaceItem(
            firm_id=firm_id,
            kind=SurfaceKind.observatory,
            item_type="observatory_test_item",
            dedup_key=uuid4().hex,
            headline="An observatory finding",
            payload={},
            rank=1,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {**firm_a_owner, "item_id": str(row.id), "item_type": row.item_type}
    finally:
        db.close()


@pytest.fixture
def firm_a_manager(client, firm_a_owner):
    """A manager in Firm A. conftest ships an owner and a staff user but no
    manager, and manager access is half the role contract here."""
    from app.core.enums import UserRole
    from app.core.security import get_password_hash
    from app.models.user import User

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=f"mgr-{uuid4().hex[:8]}@firma.com",
            hashed_password=get_password_hash("managerpass123"),
            full_name="Manager A",
            role=UserRole.manager,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        email = user.email
    finally:
        db.close()

    login = client.post(
        "/auth/token", json={"username": email, "password": "managerpass123"}
    )
    return {
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
        "firm_id": firm_id,
    }


def _events(firm_id, item_id):
    db = TestingSessionLocal()
    try:
        return db.execute(
            select(BehavioralEvent)
            .where(
                BehavioralEvent.firm_id == firm_id,
                BehavioralEvent.event_type == VIEWED,
                BehavioralEvent.entity_id == item_id,
            )
            .order_by(BehavioralEvent.occurred_at)
        ).scalars().all()
    finally:
        db.close()


def _snapshot(item_id):
    """Every column of the row, by name, so a change anywhere shows up."""
    db = TestingSessionLocal()
    try:
        row = db.execute(
            select(SurfaceItem).where(SurfaceItem.id == item_id)
        ).scalars().first()
        assert row is not None
        return {
            column.key: getattr(row, column.key)
            for column in inspect(SurfaceItem).mapper.column_attrs
        }
    finally:
        db.close()


def _view(client, headers, item_id):
    return client.post(f"/api/v1/surface-items/{item_id}/view", headers=headers)


# --- role and tenancy ------------------------------------------------------

def test_owner_gets_204(client, briefing_item):
    response = _view(client, briefing_item["headers"], briefing_item["item_id"])
    assert response.status_code == 204
    assert response.content == b""


def test_manager_gets_204(client, briefing_item, firm_a_manager):
    response = _view(client, firm_a_manager["headers"], briefing_item["item_id"])
    assert response.status_code == 204


def test_staff_gets_403(client, briefing_item, firm_a_staff):
    """Manager or above, matching both surfaces and both other actions."""
    response = _view(client, firm_a_staff["headers"], briefing_item["item_id"])
    assert response.status_code == 403


def test_another_firms_item_is_404(client, briefing_item, firm_b_owner):
    response = _view(client, firm_b_owner["headers"], briefing_item["item_id"])
    assert response.status_code == 404
    assert response.json()["detail"] == "Item not found"


def test_absent_item_is_404_with_the_identical_detail(client, briefing_item, firm_b_owner):
    """Byte for byte the same as another firm's item, so a probe cannot tell
    an id that exists from one that never did."""
    other_firm = _view(client, firm_b_owner["headers"], briefing_item["item_id"])
    absent = _view(client, firm_b_owner["headers"], str(uuid4()))

    assert absent.status_code == 404
    assert absent.json()["detail"] == "Item not found"
    assert absent.json() == other_firm.json()


# --- what the event carries ------------------------------------------------

def test_briefing_item_fires_with_kind_briefing(client, briefing_item):
    firm_id = briefing_item["firm_id"]
    item_id = briefing_item["item_id"]

    assert _view(client, briefing_item["headers"], item_id).status_code == 204

    events = _events(firm_id, item_id)
    assert len(events) == 1
    metadata = events[0].extra_metadata
    assert metadata["kind"] == "briefing"
    assert metadata["item_id"] == item_id
    assert metadata["item_type"] == briefing_item["item_type"]
    assert "appearance_count" in metadata
    assert events[0].entity_type == "surface_item"
    assert str(events[0].entity_id) == item_id


def test_observatory_item_fires_with_kind_observatory(client, observatory_item):
    firm_id = observatory_item["firm_id"]
    item_id = observatory_item["item_id"]

    assert _view(client, observatory_item["headers"], item_id).status_code == 204

    events = _events(firm_id, item_id)
    assert len(events) == 1
    metadata = events[0].extra_metadata
    assert metadata["kind"] == "observatory"
    assert metadata["item_id"] == item_id
    assert str(events[0].entity_id) == item_id


# --- writes nothing --------------------------------------------------------

def test_the_row_is_unchanged_by_a_view(client, briefing_item):
    """Every column, including updated_at.

    dismiss and implement both stamp columns; a view must not, and updated_at
    is the one that would move silently if the service ever touched the row and
    committed.
    """
    item_id = briefing_item["item_id"]
    before = _snapshot(item_id)

    assert _view(client, briefing_item["headers"], item_id).status_code == 204

    after = _snapshot(item_id)
    assert after == before


# --- no dedup --------------------------------------------------------------

def test_two_calls_fire_two_events(client, briefing_item):
    """Acted-on timing reads the first view from the log, so the second call is
    not a duplicate to be swallowed."""
    firm_id = briefing_item["firm_id"]
    item_id = briefing_item["item_id"]

    assert _view(client, briefing_item["headers"], item_id).status_code == 204
    assert _view(client, briefing_item["headers"], item_id).status_code == 204

    assert len(_events(firm_id, item_id)) == 2
