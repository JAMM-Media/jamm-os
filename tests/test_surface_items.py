# tests/test_surface_items.py

"""Behavior of the surface_items lifecycle engine.

Covers the ruled contract: tenant isolation, the row-governs-log-echoes rule,
the suppression and resurfacing matrix, resolved-in-place display, slots that
never auto-fill, the NULL-fee ranking law, and the fail-closed promotion stub.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.enums import DismissalReason, InvoiceStatus, SurfaceKind
from app.core.surface_constants import (
    BRIEFING_ACTIVE_CAP,
    BRIEFING_SUPPRESSION_DAYS,
    OBSERVATORY_SUPPRESSION_DAYS,
)
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.invoice import Invoice
from app.models.surface_item import SurfaceItem
from app.services import surface_item_service
from app.services.surface_daily_job import run_surface_generation_for_firm
from app.services.surface_generators import (
    ITEM_INVOICE_OVERDUE,
    DELTA_GOT_WORSE,
    DELTA_IMPROVED_NOT_MATERIALLY,
    DELTA_NOTHING_CHANGED,
)
from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Fixtures and factories
# ---------------------------------------------------------------------------

def _make_client(db, firm_id, name="Test Client"):
    row = Client(firm_id=firm_id, name=name, email=f"{uuid4().hex[:8]}@example.com")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _make_overdue_invoice(db, firm_id, client_id, *, days_overdue=10, total="500.00", paid="0.00"):
    invoice = Invoice(
        firm_id=firm_id,
        client_id=client_id,
        invoice_number=f"INV-{uuid4().hex[:8]}",
        subtotal=Decimal(total),
        total_amount=Decimal(total),
        amount_paid=Decimal(paid),
        status=InvoiceStatus.sent,
        due_date=date.today() - timedelta(days=days_overdue),
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def _run_job(firm_id):
    db = TestingSessionLocal()
    try:
        return run_surface_generation_for_firm(db, firm_id)
    finally:
        db.close()


def _rows(firm_id, **filters):
    db = TestingSessionLocal()
    try:
        query = db.query(SurfaceItem).filter(SurfaceItem.firm_id == firm_id)
        for key, value in filters.items():
            query = query.filter(getattr(SurfaceItem, key) == value)
        return query.order_by(SurfaceItem.rank).all()
    finally:
        db.close()


@pytest.fixture
def firm_a_with_overdue(firm_a_owner):
    """Firm A with one overdue invoice and a generated briefing row."""
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        client_row = _make_client(db, firm_id)
        client_id = client_row.id
        invoice = _make_overdue_invoice(db, firm_id, client_id)
        invoice_id = invoice.id
    finally:
        db.close()

    _run_job(firm_id)
    return {**firm_a_owner, "invoice_id": invoice_id, "client_id": client_id}


# ---------------------------------------------------------------------------
# Generation and dedup
# ---------------------------------------------------------------------------

def test_generator_creates_one_row_and_does_not_duplicate(firm_a_with_overdue):
    """The same condition twice is one row, which is what dedup_key is for."""
    firm_id = firm_a_with_overdue["firm_id"]

    rows = _rows(firm_id, item_type=ITEM_INVOICE_OVERDUE)
    assert len(rows) == 1
    assert rows[0].dedup_key == str(firm_a_with_overdue["invoice_id"])
    assert rows[0].slotted_at is not None

    _run_job(firm_id)
    _run_job(firm_id)

    rows = _rows(firm_id, item_type=ITEM_INVOICE_OVERDUE)
    assert len(rows) == 1, "a second run duplicated the condition"


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

def test_briefing_is_scoped_to_the_requesting_firm(client, firm_a_with_overdue, firm_b_owner):
    """Firm B sees its own empty briefing, never Firm A's row."""
    response_a = client.get("/api/v1/briefing", headers=firm_a_with_overdue["headers"])
    assert response_a.status_code == 200
    assert response_a.json()["count"] == 1

    response_b = client.get("/api/v1/briefing", headers=firm_b_owner["headers"])
    assert response_b.status_code == 200
    assert response_b.json()["count"] == 0
    assert response_b.json()["items"] == []


def test_cross_firm_dismiss_is_404(client, firm_a_with_overdue, firm_b_owner):
    """Another firm's item is indistinguishable from one that does not exist."""
    item_id = _rows(firm_a_with_overdue["firm_id"])[0].id

    response = client.post(
        f"/api/v1/surface-items/{item_id}/dismiss",
        headers=firm_b_owner["headers"],
        json={"reason": "not_relevant"},
    )
    assert response.status_code == 404

    missing = client.post(
        f"/api/v1/surface-items/{uuid4()}/dismiss",
        headers=firm_b_owner["headers"],
        json={"reason": "not_relevant"},
    )
    assert missing.status_code == 404
    assert response.json()["detail"] == missing.json()["detail"]


def test_cross_firm_implement_is_404(client, firm_a_with_overdue, firm_b_owner):
    item_id = _rows(firm_a_with_overdue["firm_id"])[0].id
    response = client.post(
        f"/api/v1/surface-items/{item_id}/implement", headers=firm_b_owner["headers"]
    )
    assert response.status_code == 404


def test_staff_cannot_see_either_surface(client, firm_a_staff):
    """Both surfaces are owner and manager only."""
    assert client.get("/api/v1/briefing", headers=firm_a_staff["headers"]).status_code == 403
    assert client.get("/api/v1/observatory", headers=firm_a_staff["headers"]).status_code == 403


# ---------------------------------------------------------------------------
# Row governs, log echoes
# ---------------------------------------------------------------------------

def test_dismissal_survives_a_failing_event_write(client, firm_a_with_overdue, monkeypatch):
    """The action is the row. A broken recorder cannot undo it.

    This is the single most important assertion in the file: if the event write
    were inside the same transaction, or were allowed to raise, a logging
    outage would silently start rejecting owner actions.
    """
    def exploding_log_event(**kwargs):
        raise RuntimeError("behavioral log is down")

    monkeypatch.setattr(surface_item_service, "log_event", exploding_log_event)

    item_id = _rows(firm_a_with_overdue["firm_id"])[0].id
    response = client.post(
        f"/api/v1/surface-items/{item_id}/dismiss",
        headers=firm_a_with_overdue["headers"],
        json={"reason": "already_handling"},
    )

    assert response.status_code == 200, "a failing recorder broke the action"

    row = _rows(firm_a_with_overdue["firm_id"])[0]
    assert row.dismissed_at is not None
    assert row.dismissal_reason == DismissalReason.already_handling


def test_event_fires_only_after_the_row_is_committed(client, firm_a_with_overdue, monkeypatch):
    """Ordering, not just survival: the row is durable before the echo fires.

    The fake recorder reads the row back through a SEPARATE session, so it sees
    only what has actually been committed. If the event fired first, or fired
    inside the open transaction, dismissed_at would still be NULL there.
    """
    observed = {}

    def observing_log_event(**kwargs):
        db = TestingSessionLocal()
        try:
            row = db.query(SurfaceItem).filter(
                SurfaceItem.id == kwargs["entity_id"]
            ).first()
            observed["dismissed_at_visible"] = row is not None and row.dismissed_at is not None
            observed["reason_visible"] = row.dismissal_reason if row else None
        finally:
            db.close()

    monkeypatch.setattr(surface_item_service, "log_event", observing_log_event)

    item_id = _rows(firm_a_with_overdue["firm_id"])[0].id
    client.post(
        f"/api/v1/surface-items/{item_id}/dismiss",
        headers=firm_a_with_overdue["headers"],
        json={"reason": "was_wrong"},
    )

    assert observed.get("dismissed_at_visible") is True, (
        "the event fired before the row was committed"
    )
    assert observed.get("reason_visible") == DismissalReason.was_wrong


# ---------------------------------------------------------------------------
# Dismissal reasons
# ---------------------------------------------------------------------------

def test_invalid_dismissal_reason_is_422(client, firm_a_with_overdue):
    item_id = _rows(firm_a_with_overdue["firm_id"])[0].id
    response = client.post(
        f"/api/v1/surface-items/{item_id}/dismiss",
        headers=firm_a_with_overdue["headers"],
        json={"reason": "because_i_said_so"},
    )
    assert response.status_code == 422


def test_dismiss_requires_a_reason(client, firm_a_with_overdue):
    item_id = _rows(firm_a_with_overdue["firm_id"])[0].id
    response = client.post(
        f"/api/v1/surface-items/{item_id}/dismiss",
        headers=firm_a_with_overdue["headers"],
        json={},
    )
    assert response.status_code == 422


def test_was_wrong_flags_for_review_and_starts_no_window(client, firm_a_with_overdue):
    item_id = _rows(firm_a_with_overdue["firm_id"])[0].id
    client.post(
        f"/api/v1/surface-items/{item_id}/dismiss",
        headers=firm_a_with_overdue["headers"],
        json={"reason": "was_wrong"},
    )

    row = _rows(firm_a_with_overdue["firm_id"])[0]
    assert row.flagged_for_review is True
    assert row.suppressed_until is None, "was_wrong must not start a window"


def test_not_relevant_starts_no_window_and_is_not_flagged(client, firm_a_with_overdue):
    item_id = _rows(firm_a_with_overdue["firm_id"])[0].id
    client.post(
        f"/api/v1/surface-items/{item_id}/dismiss",
        headers=firm_a_with_overdue["headers"],
        json={"reason": "not_relevant"},
    )

    row = _rows(firm_a_with_overdue["firm_id"])[0]
    assert row.suppressed_until is None
    assert row.flagged_for_review is False


@pytest.mark.parametrize("reason", ["not_relevant", "was_wrong"])
def test_permanent_dismissals_never_resurface(client, firm_a_with_overdue, reason):
    """The condition stays true, the window never comes, the item stays gone."""
    firm_id = firm_a_with_overdue["firm_id"]
    item_id = _rows(firm_id)[0].id

    client.post(
        f"/api/v1/surface-items/{item_id}/dismiss",
        headers=firm_a_with_overdue["headers"],
        json={"reason": reason},
    )

    for _ in range(3):
        _run_job(firm_id)

    row = _rows(firm_id)[0]
    assert row.slotted_at is None, "a permanently dismissed row was slotted again"

    served = client.get("/api/v1/briefing", headers=firm_a_with_overdue["headers"]).json()
    assert served["count"] == 0

    # And it still blocks a duplicate, which is how "never resurfaces" is
    # actually enforced rather than merely intended.
    assert len(_rows(firm_id, item_type=ITEM_INVOICE_OVERDUE)) == 1


# ---------------------------------------------------------------------------
# Suppression windows
# ---------------------------------------------------------------------------

def _expire_window(firm_id):
    db = TestingSessionLocal()
    try:
        row = db.query(SurfaceItem).filter(SurfaceItem.firm_id == firm_id).first()
        row.suppressed_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()


def test_already_handling_sets_a_seven_day_window_and_snapshots_values(
    client, firm_a_with_overdue
):
    item_id = _rows(firm_a_with_overdue["firm_id"])[0].id
    client.post(
        f"/api/v1/surface-items/{item_id}/dismiss",
        headers=firm_a_with_overdue["headers"],
        json={"reason": "already_handling"},
    )

    row = _rows(firm_a_with_overdue["firm_id"])[0]
    assert row.suppressed_until is not None
    days = (row.suppressed_until - row.dismissed_at).days
    assert days == BRIEFING_SUPPRESSION_DAYS
    assert row.value_at_action["balance"] == 500.0
    assert row.slotted_at is None, "a dismissed row must leave the display immediately"


def test_condition_clearing_inside_the_window_resolves_and_never_resurfaces(
    client, firm_a_with_overdue
):
    """Material improvement ends the item. It does not come back with copy."""
    firm_id = firm_a_with_overdue["firm_id"]
    item_id = _rows(firm_id)[0].id

    client.post(
        f"/api/v1/surface-items/{item_id}/dismiss",
        headers=firm_a_with_overdue["headers"],
        json={"reason": "already_handling"},
    )

    db = TestingSessionLocal()
    try:
        invoice = db.query(Invoice).filter(
            Invoice.id == firm_a_with_overdue["invoice_id"]
        ).first()
        invoice.amount_paid = Decimal("500.00")
        db.commit()
    finally:
        db.close()

    _run_job(firm_id)

    row = _rows(firm_id)[0]
    assert row.resolved_at is not None
    assert row.payload.get("resolved_outcome") == "Paid"

    _expire_window(firm_id)
    _run_job(firm_id)

    row = _rows(firm_id)[0]
    assert row.resolved_at is not None
    assert row.slotted_at is None, "a resolved item resurfaced at window expiry"


@pytest.mark.parametrize(
    "mutation,expected_shape",
    [
        (None, DELTA_NOTHING_CHANGED),
        ("worse", DELTA_GOT_WORSE),
        ("partial", DELTA_IMPROVED_NOT_MATERIALLY),
    ],
)
def test_window_expiry_resurfaces_with_the_right_delta_shape(
    client, firm_a_with_overdue, mutation, expected_shape
):
    """The three shapes, computed against value_at_action and nothing else."""
    firm_id = firm_a_with_overdue["firm_id"]
    item_id = _rows(firm_id)[0].id

    client.post(
        f"/api/v1/surface-items/{item_id}/dismiss",
        headers=firm_a_with_overdue["headers"],
        json={"reason": "already_handling"},
    )

    if mutation:
        db = TestingSessionLocal()
        try:
            invoice = db.query(Invoice).filter(
                Invoice.id == firm_a_with_overdue["invoice_id"]
            ).first()
            if mutation == "worse":
                invoice.total_amount = Decimal("800.00")
            else:
                invoice.amount_paid = Decimal("200.00")
            db.commit()
        finally:
            db.close()

    _expire_window(firm_id)
    _run_job(firm_id)

    row = _rows(firm_id)[0]
    assert row.resolved_at is None
    assert row.suppressed_until is None, "the window did not expire"
    assert row.payload["delta"]["shape"] == expected_shape
    assert row.slotted_at is not None, "the item did not come back into the display"


def test_implement_uses_seven_days_on_the_briefing(client, firm_a_with_overdue):
    item_id = _rows(firm_a_with_overdue["firm_id"])[0].id
    response = client.post(
        f"/api/v1/surface-items/{item_id}/implement",
        headers=firm_a_with_overdue["headers"],
    )
    assert response.status_code == 200

    row = _rows(firm_a_with_overdue["firm_id"])[0]
    assert row.implemented_at is not None
    assert (row.suppressed_until - row.implemented_at).days == BRIEFING_SUPPRESSION_DAYS
    assert row.value_at_action["balance"] == 500.0
    assert row.slotted_at is None


def test_implement_uses_fourteen_days_in_the_observatory(client, firm_a_owner):
    """Same action, different window, chosen by kind and not by the caller."""
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        row = SurfaceItem(
            firm_id=firm_id,
            kind=SurfaceKind.observatory,
            item_type="placeholder_technique",
            dedup_key=str(uuid4()),
            headline="A standing signal",
            payload={"measured": {"value": 3}},
            rank=0,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        item_id = row.id
    finally:
        db.close()

    response = client.post(
        f"/api/v1/surface-items/{item_id}/implement", headers=firm_a_owner["headers"]
    )
    assert response.status_code == 200

    db = TestingSessionLocal()
    try:
        row = db.query(SurfaceItem).filter(SurfaceItem.id == item_id).first()
        assert (row.suppressed_until - row.implemented_at).days == OBSERVATORY_SUPPRESSION_DAYS
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Display behavior
# ---------------------------------------------------------------------------

def test_resolved_in_place_keeps_its_slot_and_does_not_reshuffle(
    client, firm_a_with_overdue
):
    """A row that cleared this morning stays where it was, marked resolved."""
    firm_id = firm_a_with_overdue["firm_id"]

    db = TestingSessionLocal()
    try:
        invoice = db.query(Invoice).filter(
            Invoice.id == firm_a_with_overdue["invoice_id"]
        ).first()
        invoice.amount_paid = Decimal("500.00")
        db.commit()
    finally:
        db.close()

    body = client.get("/api/v1/briefing", headers=firm_a_with_overdue["headers"]).json()

    assert body["count"] == 1, "the row left the display instead of resolving in place"
    assert body["resolved_in_place"] == 1
    assert body["items"][0]["resolved_at"] is not None
    assert body["items"][0]["payload"]["resolved_outcome"] == "Paid"


def test_appearance_count_increments_once_per_day(client, firm_a_with_overdue):
    """It counts times served, and serving twice in a day is still one day."""
    headers = firm_a_with_overdue["headers"]

    client.get("/api/v1/briefing", headers=headers)
    first = _rows(firm_a_with_overdue["firm_id"])[0].appearance_count

    client.get("/api/v1/briefing", headers=headers)
    second = _rows(firm_a_with_overdue["firm_id"])[0].appearance_count

    assert first == 1
    assert second == 1, "appearance_count incremented twice in one day"


def test_slots_do_not_auto_fill_and_promote_next_fills_exactly_one(
    client, firm_a_owner
):
    """An opened slot stays open until the owner asks for another item."""
    firm_id = firm_a_owner["firm_id"]

    db = TestingSessionLocal()
    try:
        client_row = _make_client(db, firm_id)
        for index in range(BRIEFING_ACTIVE_CAP + 2):
            _make_overdue_invoice(db, firm_id, client_row.id, days_overdue=30 - index)
    finally:
        db.close()

    _run_job(firm_id)

    slotted = [row for row in _rows(firm_id) if row.slotted_at is not None]
    assert len(slotted) == BRIEFING_ACTIVE_CAP

    client.post(
        f"/api/v1/surface-items/{slotted[0].id}/dismiss",
        headers=firm_a_owner["headers"],
        json={"reason": "not_relevant"},
    )

    body = client.get("/api/v1/briefing", headers=firm_a_owner["headers"]).json()
    assert body["count"] == BRIEFING_ACTIVE_CAP - 1, "the slot auto-filled"

    promoted = client.post(
        "/api/v1/briefing/promote-next", headers=firm_a_owner["headers"]
    ).json()
    assert promoted["promoted"] is True
    assert promoted["item"] is not None

    body = client.get("/api/v1/briefing", headers=firm_a_owner["headers"]).json()
    assert body["count"] == BRIEFING_ACTIVE_CAP, "promote-next filled more or less than one"


def test_promote_next_is_honest_when_nothing_is_waiting(client, firm_a_with_overdue):
    """Running out of items is a normal morning, not an error."""
    response = client.post(
        "/api/v1/briefing/promote-next", headers=firm_a_with_overdue["headers"]
    )
    assert response.status_code == 200
    body = response.json()
    assert body["promoted"] is False
    assert body["item"] is None
    assert body["detail"]


# ---------------------------------------------------------------------------
# Observatory
# ---------------------------------------------------------------------------

def test_observatory_is_empty_and_says_so_unambiguously(client, firm_a_with_overdue):
    """Day one is empty by construction, and the shape makes that explicit."""
    body = client.get("/api/v1/observatory", headers=firm_a_with_overdue["headers"]).json()

    assert body["items"] == []
    assert body["count"] == 0
    assert body["is_empty"] is True
    assert body["intelligence_pending"] is True


def test_briefing_reports_the_pending_intelligence_state(client, firm_a_with_overdue):
    body = client.get("/api/v1/briefing", headers=firm_a_with_overdue["headers"]).json()
    assert body["intelligence_pending"] is True


def test_a_resolved_row_keeps_its_slot_for_the_day_then_leaves(client, firm_a_with_overdue):
    """Resolved in place is for the DAY, not forever.

    The row stays in its slot once it clears, so the list does not reshuffle
    under the reader. The next morning's generation is what takes the slot
    back. Without that second half, every item a firm ever resolved would stay
    pinned to the briefing permanently, and the cap would fill with history.
    """
    firm_id = firm_a_with_overdue["firm_id"]
    headers = firm_a_with_overdue["headers"]

    db = TestingSessionLocal()
    try:
        invoice = db.query(Invoice).filter(
            Invoice.id == firm_a_with_overdue["invoice_id"]
        ).first()
        invoice.amount_paid = Decimal("500.00")
        db.commit()
    finally:
        db.close()

    # Same day: it resolves in place and holds its slot.
    body = client.get("/api/v1/briefing", headers=headers).json()
    assert body["count"] == 1
    assert body["items"][0]["resolved_at"] is not None

    # Next morning's generation.
    _run_job(firm_id)

    body = client.get("/api/v1/briefing", headers=headers).json()
    assert body["count"] == 0, "a resolved row kept its slot past the day it resolved"

    row = _rows(firm_id)[0]
    assert row.resolved_at is not None
    assert row.slotted_at is None
